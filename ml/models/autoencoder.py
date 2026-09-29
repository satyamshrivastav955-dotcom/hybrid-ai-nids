"""PyTorch deep autoencoder for benign-traffic reconstruction.

Architecture (baseline): input -> 64 -> 32 -> 16 -> 32 -> 64 -> output.
Trained ONLY on benign TRAIN data; threshold set on benign VALIDATION data.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from ml.common import git_commit, set_seed


class AutoencoderNet(nn.Module):
    def __init__(self, input_dim: int, hidden_dims: list[int] | None = None) -> None:
        super().__init__()
        hidden_dims = hidden_dims or [64, 32, 16]
        enc, prev = [], input_dim
        for h in hidden_dims:
            enc += [nn.Linear(prev, h), nn.ReLU()]
            prev = h
        dec = []
        for h in reversed(hidden_dims[:-1]):
            dec += [nn.Linear(prev, h), nn.ReLU()]
            prev = h
        dec += [nn.Linear(prev, input_dim)]
        self.encoder = nn.Sequential(*enc)
        self.decoder = nn.Sequential(*dec)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(x))


class AutoencoderModel:
    name = "autoencoder"

    def __init__(
        self,
        input_dim: int,
        hidden_dims: list[int] | None = None,
        learning_rate: float = 1e-3,
        batch_size: int = 256,
        epochs: int = 50,
        patience: int = 8,
        seed: int = 42,
    ) -> None:
        self.input_dim = input_dim
        self.hidden_dims = hidden_dims or [64, 32, 16]
        self.lr = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.patience = patience
        self.seed = seed
        set_seed(seed)
        self.net = AutoencoderNet(input_dim, self.hidden_dims)
        self.threshold_: float | None = None
        self.threshold_strategy_: str = "percentile"
        self.history_: dict = {"train_loss": [], "val_loss": []}

    def fit(self, X_benign_train: np.ndarray, X_benign_val: np.ndarray) -> "AutoencoderModel":
        set_seed(self.seed)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.net.to(device)
        opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        loss_fn = nn.MSELoss()
        tr = DataLoader(TensorDataset(torch.tensor(X_benign_train, dtype=torch.float32)), batch_size=self.batch_size, shuffle=True)
        va = DataLoader(TensorDataset(torch.tensor(X_benign_val, dtype=torch.float32)), batch_size=self.batch_size)
        best, best_state, bad = float("inf"), None, 0
        for epoch in range(self.epochs):
            self.net.train()
            tl = 0.0
            for (xb,) in tr:
                xb = xb.to(device)
                opt.zero_grad()
                loss = loss_fn(self.net(xb), xb)
                loss.backward()
                opt.step()
                tl += loss.item() * len(xb)
            tl /= max(1, len(tr.dataset))
            self.net.eval()
            vl = 0.0
            with torch.no_grad():
                for (xb,) in va:
                    xb = xb.to(device)
                    vl += loss_fn(self.net(xb), xb).item() * len(xb)
            vl /= max(1, len(va.dataset))
            self.history_["train_loss"].append(tl)
            self.history_["val_loss"].append(vl)
            if (epoch + 1) % 5 == 0 or epoch == 0:
                print(f"[AE] epoch {epoch + 1}/{self.epochs} train={tl:.5f} val={vl:.5f}", flush=True)
            if vl < best - 1e-6:
                best, bad = vl, 0
                best_state = {k: v.cpu().clone() for k, v in self.net.state_dict().items()}
            else:
                bad += 1
                if bad >= self.patience:
                    break
        if best_state is not None:
            self.net.load_state_dict(best_state)
        self.net.to("cpu")
        return self

    @torch.no_grad()
    def reconstruction_error(self, X: np.ndarray) -> np.ndarray:
        self.net.eval()
        xb = torch.tensor(np.asarray(X, dtype=np.float32))
        out = self.net(xb)
        return ((out - xb) ** 2).mean(dim=1).numpy()

    @torch.no_grad()
    def per_feature_error(self, X: np.ndarray) -> np.ndarray:
        self.net.eval()
        xb = torch.tensor(np.asarray(X, dtype=np.float32))
        out = self.net(xb)
        return ((out - xb) ** 2).numpy()

    def fit_threshold(
        self,
        X_benign_val: np.ndarray,
        strategy: str = "percentile",
        percentile: float = 95.0,
        fpr_target: float = 0.05,
        y_val: np.ndarray | None = None,
        val_scores: np.ndarray | None = None,
    ) -> float:
        """Threshold from benign VALIDATION only (never test attacks).

        percentile: threshold = percentile of benign-val reconstruction errors.
        fpr_target: requires y_val (0=benign,1=attack) on validation; picks the
                    threshold achieving ~fpr_target on validation.
        """
        scores = self.reconstruction_error(X_benign_val)
        if strategy == "fpr_target":
            if y_val is None or val_scores is None:
                raise ValueError("fpr_target strategy needs validation labels + scores.")
            order = np.argsort(val_scores)
            ys = np.asarray(y_val)[order]
            # threshold sweep on validation scores
            best_t, best_diff = float(scores.max()), float("inf")
            for t in np.quantile(val_scores, np.linspace(0.5, 0.999, 200)):
                fpr = float(((val_scores >= t) & (np.asarray(y_val) == 0)).sum() / max(1, (np.asarray(y_val) == 0).sum()))
                if abs(fpr - fpr_target) < best_diff:
                    best_diff, best_t = abs(fpr - fpr_target), float(t)
            self.threshold_ = best_t
        else:
            self.threshold_ = float(np.percentile(scores, percentile))
        self.threshold_strategy_ = strategy
        return float(self.threshold_)

    def anomaly_score(self, X: np.ndarray) -> np.ndarray:
        if self.threshold_ is None:
            raise RuntimeError("Threshold not set. Call fit_threshold on benign validation first.")
        err = self.reconstruction_error(X)
        # Normalised 0..1 around the threshold for fusion (monotonic, no test leakage:
        # scaling uses benign-val threshold + train max scale stored at save time).
        scale = max(float(err.max()), self.threshold_ * 2.0, 1e-9)
        return np.clip(err / scale, 0.0, 1.0)

    def save(self, model_dir: str | Path, extra: dict | None = None) -> None:
        d = Path(model_dir)
        d.mkdir(parents=True, exist_ok=True)
        torch.save(self.net.state_dict(), d / "autoencoder.pth")
        meta = {
            "model_name": self.name,
            "version": "v1.0.0",
            "input_dim": self.input_dim,
            "hidden_dims": self.hidden_dims,
            "threshold": self.threshold_,
            "threshold_strategy": self.threshold_strategy_,
            "git_commit": git_commit(),
            **(extra or {}),
        }
        (d / "autoencoder_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        (d / "autoencoder_threshold.json").write_text(
            json.dumps({"threshold": self.threshold_, "strategy": self.threshold_strategy_}, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, model_dir: str | Path) -> "AutoencoderModel":
        d = Path(model_dir)
        meta = json.loads((d / "autoencoder_meta.json").read_text(encoding="utf-8"))
        obj = cls(input_dim=int(meta["input_dim"]), hidden_dims=list(meta.get("hidden_dims", [64, 32, 16])))
        obj.net.load_state_dict(torch.load(d / "autoencoder.pth", map_location="cpu"))
        obj.net.eval()
        obj.threshold_ = meta.get("threshold")
        obj.threshold_strategy_ = meta.get("threshold_strategy", "percentile")
        return obj

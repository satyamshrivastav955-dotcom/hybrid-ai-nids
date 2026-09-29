"""LSTM temporal model: sequence [x(t-9)..x(t)] -> attack probability."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from ml.common import git_commit, set_seed


class LSTMNet(nn.Module):
    def __init__(self, input_dim: int, hidden_size: int = 64, num_layers: int = 1, dropout: float = 0.2) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_size, num_layers=num_layers, batch_first=True,
                            dropout=dropout if num_layers > 1 else 0.0)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.head(self.drop(out[:, -1, :])).squeeze(-1)


class LSTMModel:
    name = "lstm"

    def __init__(self, input_dim: int, seq_len: int = 10, hidden_size: int = 64,
                 num_layers: int = 1, dropout: float = 0.2, learning_rate: float = 1e-3,
                 batch_size: int = 256, epochs: int = 30, patience: int = 6, seed: int = 42) -> None:
        self.input_dim = input_dim
        self.seq_len = seq_len
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.lr = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.patience = patience
        self.seed = seed
        set_seed(seed)
        self.net = LSTMNet(input_dim, hidden_size, num_layers, dropout)

    def fit(self, X_seq: np.ndarray, y_seq: np.ndarray,
            X_val: np.ndarray, y_val: np.ndarray) -> "LSTMModel":
        set_seed(self.seed)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.net.to(device)
        opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        loss_fn = nn.BCEWithLogitsLoss()
        tr = DataLoader(TensorDataset(torch.tensor(X_seq, dtype=torch.float32),
                                      torch.tensor(y_seq.astype(float), dtype=torch.float32)),
                        batch_size=self.batch_size, shuffle=True)
        va = DataLoader(TensorDataset(torch.tensor(X_val, dtype=torch.float32),
                                      torch.tensor(y_val.astype(float), dtype=torch.float32)),
                        batch_size=self.batch_size)
        best, best_state, bad = float("inf"), None, 0
        for epoch in range(self.epochs):
            self.net.train()
            for xb, yb in tr:
                xb, yb = xb.to(device), yb.to(device)
                opt.zero_grad()
                loss = loss_fn(self.net(xb), yb)
                loss.backward()
                opt.step()
            self.net.eval()
            vl, n = 0.0, 0
            with torch.no_grad():
                for xb, yb in va:
                    xb, yb = xb.to(device), yb.to(device)
                    vl += loss_fn(self.net(xb), yb).item() * len(xb)
                    n += len(xb)
            vl /= max(1, n)
            if (epoch + 1) % 5 == 0 or epoch == 0:
                print(f"[LSTM] epoch {epoch + 1}/{self.epochs} val={vl:.5f}", flush=True)
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
    def predict_proba(self, X_seq: np.ndarray) -> np.ndarray:
        self.net.eval()
        xb = torch.tensor(np.asarray(X_seq, dtype=np.float32))
        logits = self.net(xb).numpy()
        return 1.0 / (1.0 + np.exp(-logits))

    def save(self, model_dir: str | Path, extra: dict | None = None) -> None:
        d = Path(model_dir)
        d.mkdir(parents=True, exist_ok=True)
        torch.save(self.net.state_dict(), d / "lstm_model.pth")
        meta = {"model_name": self.name, "version": "v1.0.0", "input_dim": self.input_dim,
                "seq_len": self.seq_len, "hidden_size": self.hidden_size,
                "num_layers": self.num_layers, "dropout": self.dropout,
                "git_commit": git_commit(), **(extra or {})}
        (d / "lstm_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    @classmethod
    def load(cls, model_dir: str | Path) -> "LSTMModel":
        d = Path(model_dir)
        meta = json.loads((d / "lstm_meta.json").read_text(encoding="utf-8"))
        obj = cls(input_dim=int(meta["input_dim"]), seq_len=int(meta.get("seq_len", 10)),
                  hidden_size=int(meta.get("hidden_size", 64)),
                  num_layers=int(meta.get("num_layers", 1)),
                  dropout=float(meta.get("dropout", 0.2)))
        obj.net.load_state_dict(torch.load(d / "lstm_model.pth", map_location="cpu"))
        obj.net.eval()
        return obj

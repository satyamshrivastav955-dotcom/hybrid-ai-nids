"""Print a compact summary of all experiment results (console-safe)."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
res = Path("experiments/results")


def show_standard():
    m = json.load(open(res / "standard_metrics.json"))
    print(f"== standard (n_test={m['n_test']}) ==")
    for k, v in m["metrics"].items():
        print(f"{k:12s} acc={v.get('accuracy')} prec={v.get('precision')} "
              f"rec={v.get('recall')} f1={v.get('f1')} mcc={v.get('mcc')} "
              f"roc={v.get('roc_auc')} pr={v.get('pr_auc')} fpr={v.get('fpr')}")


def show_unseen():
    m = json.load(open(res / "unseen_attack_metrics.json"))
    print("== unseen_attack ==")
    print("holdout:", m.get("holdout_families"))
    for part in ("known_attack_performance", "unseen_attack_performance"):
        v = m[part]
        print(f"{part:26s} n={v.get('n')} prec={v.get('precision')} "
              f"rec={v.get('recall')} f1={v.get('f1')} fpr={v.get('fpr')}")


def show_temporal():
    m = json.load(open(res / "temporal_metrics.json"))
    print("== temporal ==")
    for w, v in m["windows"].items():
        print(f"{w:6s} n={v.get('n')} f1={v.get('f1')} pr_auc={v.get('pr_auc')} fpr={v.get('fpr')}")


def show_ablation():
    m = json.load(open(res / "ablation_metrics.json"))
    print("== ablation ==")
    for k, v in m["results"].items():
        print(f"{k:22s} f1={v.get('f1')} rec={v.get('recall')} fpr={v.get('fpr')} {v.get('note', '')}")


def show_latency():
    m = json.load(open(res / "latency_metrics.json"))
    print(f"== latency (n={m.get('n_rows')}) ==")
    for stage, v in m["stages"].items():
        print(f"{stage:16s} mean={v.get('mean_ms')}ms p95={v.get('p95_ms')}ms "
              f"{('thr=' + str(v.get('throughput_rows_per_sec')) + '/s') if 'throughput_rows_per_sec' in v else ''}")


def show_drift():
    m = json.load(open(res / "drift_metrics.json"))
    print("== drift ==")
    print("aggregate_psi:", m["drift"].get("aggregate_psi"), m["drift"].get("status"))
    for name, v in m["performance"].items():
        print(f"{name:16s} f1={v.get('f1')} fpr={v.get('fpr')}")


if __name__ == "__main__":
    for fn in (show_standard, show_unseen, show_temporal, show_ablation, show_latency, show_drift):
        try:
            fn()
        except FileNotFoundError as e:
            print("missing:", e)
        print()

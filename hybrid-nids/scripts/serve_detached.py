"""Detached server launcher (Windows-safe): spawns uvicorn/frontend fully detached.

Usage:
  python scripts/serve_detached.py backend   # :8000
  python scripts/serve_detached.py frontend  # :5173
Logs: backend.out.log / frontend.out.log
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DETACHED = 0x00000008  # DETACHED_PROCESS
NEW_GROUP = 0x00000200  # CREATE_NEW_PROCESS_GROUP


def launch(cmd, cwd, out_log, shell=False):
    with open(out_log, "ab") as log:
        p = subprocess.Popen(
            cmd, cwd=str(cwd), stdout=log, stderr=subprocess.STDOUT,
            creationflags=DETACHED | NEW_GROUP, close_fds=True, shell=shell,
        )
    print(f"launched pid={p.pid}: {cmd} -> {out_log}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "backend"
    if which == "backend":
        launch([sys.executable, "-m", "uvicorn", "backend.app.main:app",
                "--host", "0.0.0.0", "--port", "8000"], ROOT, ROOT / "backend.out.log")
    elif which == "frontend":
        launch("npm run dev -- --host 0.0.0.0 --port 5173",
               ROOT / "frontend", ROOT / "frontend.out.log", shell=True)
    elif which == "train":
        extra = sys.argv[2:]
        launch([sys.executable, "scripts/train_all.py", *extra],
               ROOT, ROOT / "train.out.log")
    else:
        raise SystemExit("unknown target: backend | frontend")

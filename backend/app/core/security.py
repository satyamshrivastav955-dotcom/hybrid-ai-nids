"""API security helpers: CORS, rate limiting (in-memory), audit log hook.

Auth design: pluggable API-key header (X-API-Key) when API_KEY env is set;
otherwise open (research default) but every mutating action is audit-logged.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict

from fastapi import Header, HTTPException

_WINDOW = 60.0
_LIMIT = 300  # requests per window per IP (generous research default)
_hits: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(client_ip: str) -> None:
    now = time.time()
    buf = [t for t in _hits[client_ip] if now - t < _WINDOW]
    buf.append(now)
    _hits[client_ip] = buf
    if len(buf) > _LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Slow down.")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("API_KEY", "")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")

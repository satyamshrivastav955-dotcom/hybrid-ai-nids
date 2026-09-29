"""Central application configuration (env + YAML defaults). Secrets via env only."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = f"sqlite:///{ROOT / 'nids.db'}"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    model_dir: str = str(ROOT / "models")
    demo_mode: bool = False
    ingestion_mode: str = "dataset"
    threat_intel_provider: str = "mock"
    backend_version: str = "1.0.0"

    class Config:
        env_file = str(ROOT / ".env")
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()

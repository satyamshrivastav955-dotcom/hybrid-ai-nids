"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router, service, ws_router
from backend.app.core.config import get_settings
from backend.app.core.logging import setup_logging
from backend.app.db.database import init_db

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Resolve via module so test fixtures (or future hot-swap) that rebind
    # backend.app.api.routes.service take effect here too.
    from backend.app.api import routes as _routes
    ok = _routes.service.load()
    logger.info("Startup complete. models_loaded=%s", ok)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Hybrid NIDS", version=settings.backend_version,
                  description="Hybrid AI Network Intrusion Detection & Adaptive SOC (research-grade)",
                  lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(ws_router)
    return app


app = create_app()

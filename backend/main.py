"""GenomeInsight FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes.column_presets import router as column_presets_router
from backend.api.routes.databases import router as databases_router
from backend.api.routes.ingest import router as ingest_router
from backend.api.routes.samples import router as samples_router
from backend.api.routes.setup import router as setup_router
from backend.api.routes.variants import router as variants_router
from backend.config import get_settings
from backend.db.connection import get_registry, reset_registry

logger = logging.getLogger(__name__)

VERSION = "0.1.0"


# ── Lifespan ──────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle for the FastAPI app."""
    # Startup: initialize the DB registry (creates reference engine, etc.)
    get_registry()
    logger.info("DBRegistry initialised (reference.db engine ready)")
    yield
    # Shutdown: dispose all engines
    reset_registry()
    logger.info("DBRegistry disposed - all engines closed")


# ── App factory ───────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title="GenomeInsight",
        version=VERSION,
        lifespan=lifespan,
    )

    # CORS - restrict to localhost dev origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:8000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create a fresh API router per app instance to avoid duplicate routes
    api_router = APIRouter(prefix="/api")

    @api_router.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint. Always exempt from auth."""
        return {"status": "ok", "version": VERSION}

    # API routes (must be included BEFORE static mount)
    api_router.include_router(column_presets_router)
    api_router.include_router(databases_router)
    api_router.include_router(ingest_router)
    api_router.include_router(samples_router)
    api_router.include_router(setup_router)
    api_router.include_router(variants_router)
    app.include_router(api_router)

    # Static files - SPA fallback (only if frontend has been built)
    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")

    return app


app = create_app()

# ── Direct execution ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )

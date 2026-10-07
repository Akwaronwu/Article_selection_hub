"""FastAPI application factory.

``create_app`` wires configuration, CORS, the API router, and startup tasks
(DB bootstrap). Development server: ``uvicorn app.main:app --reload``
(run from ``backend/`` inside the virtualenv).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.config import Settings, get_settings
from app.db import configure_engine, init_db


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI application (injectable settings keep tests isolated)."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_engine(settings.database_url)
        if settings.auto_create_tables:
            init_db()
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version or __version__,
        description=(
            "AI-assisted systematic literature review platform. "
            "AI recommends; researchers decide. Every AI output is evidence-linked "
            "and overridable."
        ),
        openapi_url=f"{settings.api_v1_prefix}/openapi.json" if settings.docs_enabled else None,
        docs_url=f"{settings.api_v1_prefix}/docs" if settings.docs_enabled else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.state.settings = settings
    return app


app = create_app()

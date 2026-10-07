"""Health and readiness endpoints."""

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app import __version__
from app.db import database_reachable

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Payload returned by ``GET /health``."""

    status: str
    service: str
    version: str
    environment: str
    database: str


@router.get("/health", response_model=HealthResponse, summary="Service health probe")
def health(request: Request, response: Response) -> HealthResponse:
    """Liveness/readiness check: verifies configuration and DB connectivity.

    Returns HTTP 503 when the database is unreachable so orchestrators and
    tests can distinguish "running" from "healthy". Settings are read from
    ``app.state`` (the injected instance), not from the global cache, so test
    applications report their own environment.
    """
    settings = request.app.state.settings
    db_ok = database_reachable()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        service=settings.app_name,
        version=__version__,
        environment=settings.environment,
        database="reachable" if db_ok else "unreachable",
    )

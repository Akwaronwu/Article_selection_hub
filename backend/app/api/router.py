"""API v1 router aggregation.

Every feature router is registered here; ``main.py`` mounts the whole
aggregate under ``/api/v1`` so versioning stays consistent.
"""

from fastapi import APIRouter

from app.api import auth, health, jobs, members, projects, protocol, studies

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(members.router)
api_router.include_router(protocol.router)
api_router.include_router(studies.router)
api_router.include_router(jobs.router)

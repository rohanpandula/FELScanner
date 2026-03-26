"""
API v1 Routes
All endpoint routers for version 1 of the API
"""
from fastapi import APIRouter

from app.api.v1 import (
    scan,
    movies,
    downloads,
    settings,
    collections,
    status,
    metadata,
    connections,
    ipt,
    analytics,
    release_groups,
    activity,
)

# Create main API v1 router
api_router = APIRouter()

# Include all sub-routers
api_router.include_router(status.router, prefix="/status", tags=["status"])
api_router.include_router(scan.router, prefix="/scan", tags=["scan"])
api_router.include_router(movies.router, prefix="/movies", tags=["movies"])
api_router.include_router(metadata.router, prefix="/metadata", tags=["metadata"])
api_router.include_router(collections.router, prefix="/collections", tags=["collections"])
api_router.include_router(downloads.router, prefix="/downloads", tags=["downloads"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(connections.router, prefix="/connections", tags=["connections"])
api_router.include_router(ipt.router, prefix="/ipt", tags=["ipt"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(release_groups.router, prefix="/release-groups", tags=["release-groups"])
api_router.include_router(activity.router, prefix="/activity", tags=["activity"])

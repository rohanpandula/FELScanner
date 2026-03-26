"""
Status API Endpoints
Application status, version info, system health
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.movie_service import MovieService
from app.services.scan_service import ScanService

router = APIRouter()
logger = get_logger(__name__)


@router.get("", response_model=dict[str, Any])
@router.get("/", response_model=dict[str, Any], include_in_schema=False)
async def get_status(db: AsyncSession = Depends(get_db)):
    """
    Get application status

    Returns current status of the application including:
    - Application metadata
    - Scan status
    - Library statistics
    - System information
    """
    settings = get_settings()

    # Get scan service status
    scan_service = ScanService(db)
    is_scanning = await scan_service.is_scan_running()
    current_scan = await scan_service.get_current_scan()

    # Get last scan
    scans, _ = await scan_service.get_scan_history(limit=1)
    last_scan = scans[0] if scans else None

    # Get library statistics
    movie_service = MovieService(db)
    stats = await movie_service.get_statistics()

    return {
        "app": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "debug": settings.DEBUG,
            "environment": "development" if settings.is_development else "production",
        },
        "scan": {
            "is_running": is_scanning,
            "current_scan_id": current_scan.id if current_scan else None,
            "current_scan_started": current_scan.started_at if current_scan else None,
            "last_scan_completed": last_scan.completed_at if last_scan else None,
            "last_scan_status": last_scan.status if last_scan else None,
        },
        "library": stats,
        "integrations": {
            "plex_configured": bool(settings.PLEX_URL and settings.PLEX_TOKEN),
            "telegram_enabled": settings.TELEGRAM_ENABLED,
            "qbittorrent_configured": bool(settings.QBITTORRENT_HOST),
            "radarr_configured": bool(settings.RADARR_URL),
        },
    }


@router.get("/version", response_model=dict[str, str])
async def get_version():
    """
    Get application version information

    Returns version string and build metadata.
    """
    settings = get_settings()

    return {
        "version": settings.APP_VERSION,
        "name": settings.APP_NAME,
    }

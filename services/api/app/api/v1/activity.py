"""
Activity Feed API Endpoints
Chronological timeline of all significant events
"""
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.services.activity_service import ActivityService

router = APIRouter()
logger = get_logger(__name__)


@router.get("")
@router.get("/", include_in_schema=False)
async def get_activity_feed(
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset"),
    event_type: str | None = Query(None, description="Filter by event type"),
    severity: str | None = Query(None, description="Filter by severity"),
    movie_id: int | None = Query(None, description="Filter by movie ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the activity feed with filtering and pagination.

    Event types: movie_added, movie_upgraded, movie_removed,
    download_approved, download_declined, scan_completed,
    collection_changed, upgrade_available, ipt_scan
    """
    service = ActivityService(db)
    events, total = await service.get_feed(
        limit=limit,
        offset=offset,
        event_type=event_type,
        severity=severity,
        movie_id=movie_id,
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "title": e.title,
                "description": e.description,
                "severity": e.severity,
                "movie_id": e.movie_id,
                "movie_title": e.movie_title,
                "movie_year": e.movie_year,
                "related_id": e.related_id,
                "related_type": e.related_type,
                "quality_before": e.quality_before,
                "quality_after": e.quality_after,
                "metadata": e.extra_data,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }


@router.get("/summary")
async def get_activity_summary(
    hours: int = Query(24, ge=1, le=720, description="Hours to look back"),
    db: AsyncSession = Depends(get_db),
):
    """Get summary of recent activity"""
    service = ActivityService(db)
    return await service.get_recent_summary(hours)


@router.get("/types")
async def get_event_type_counts(db: AsyncSession = Depends(get_db)):
    """Get count of events by type"""
    service = ActivityService(db)
    return await service.get_event_type_counts()


@router.get("/movie/{movie_id}")
async def get_movie_timeline(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all activity events for a specific movie"""
    service = ActivityService(db)
    events = await service.get_movie_timeline(movie_id)

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "title": e.title,
            "description": e.description,
            "severity": e.severity,
            "quality_before": e.quality_before,
            "quality_after": e.quality_after,
            "metadata": e.extra_data,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]

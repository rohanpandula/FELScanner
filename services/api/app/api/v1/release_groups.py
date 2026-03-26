"""
Release Groups API Endpoints
Release group reputation, preferences, and statistics
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.services.release_group_service import ReleaseGroupService

router = APIRouter()
logger = get_logger(__name__)


class GroupPreferenceUpdate(BaseModel):
    """Update preference for a release group"""
    is_preferred: bool | None = None
    is_blocked: bool | None = None
    priority: int | None = None
    notes: str | None = None


@router.get("")
@router.get("/", include_in_schema=False)
async def list_release_groups(
    sort_by: str = Query("total_releases_seen", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order"),
    preferred_only: bool = Query(False, description="Only show preferred groups"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all known release groups with stats.

    Groups are automatically discovered from IPT scan results.
    """
    service = ReleaseGroupService(db)
    groups = await service.get_all_groups(sort_by, sort_order, preferred_only)
    return [
        {
            "id": g.id,
            "group_name": g.group_name,
            "is_preferred": g.is_preferred,
            "is_blocked": g.is_blocked,
            "priority": g.priority,
            "avg_file_size_gb": float(g.avg_file_size_gb) if g.avg_file_size_gb else None,
            "total_releases_seen": g.total_releases_seen,
            "total_downloads": g.total_downloads,
            "avg_quality_score": float(g.avg_quality_score) if g.avg_quality_score else None,
            "first_seen_at": g.first_seen_at.isoformat() if g.first_seen_at else None,
            "last_seen_at": g.last_seen_at.isoformat() if g.last_seen_at else None,
            "notes": g.notes,
        }
        for g in groups
    ]


@router.get("/summary")
async def get_group_summary(db: AsyncSession = Depends(get_db)):
    """Get summary stats across all release groups"""
    service = ReleaseGroupService(db)
    return await service.get_group_stats_summary()


@router.get("/preferred")
async def get_preferred_groups(db: AsyncSession = Depends(get_db)):
    """Get list of preferred group names"""
    service = ReleaseGroupService(db)
    return await service.get_preferred_groups()


@router.get("/blocked")
async def get_blocked_groups(db: AsyncSession = Depends(get_db)):
    """Get list of blocked group names"""
    service = ReleaseGroupService(db)
    return await service.get_blocked_groups()


@router.get("/{group_name}")
async def get_release_group(
    group_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific release group"""
    service = ReleaseGroupService(db)
    group = await service.get_group(group_name)
    if not group:
        raise HTTPException(status_code=404, detail="Release group not found")

    return {
        "id": group.id,
        "group_name": group.group_name,
        "is_preferred": group.is_preferred,
        "is_blocked": group.is_blocked,
        "priority": group.priority,
        "avg_file_size_gb": float(group.avg_file_size_gb) if group.avg_file_size_gb else None,
        "total_releases_seen": group.total_releases_seen,
        "total_downloads": group.total_downloads,
        "avg_quality_score": float(group.avg_quality_score) if group.avg_quality_score else None,
        "first_seen_at": group.first_seen_at.isoformat() if group.first_seen_at else None,
        "last_seen_at": group.last_seen_at.isoformat() if group.last_seen_at else None,
        "notes": group.notes,
        "metadata": group.extra_data,
    }


@router.patch("/{group_name}")
async def update_group_preference(
    group_name: str,
    body: GroupPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update preference for a release group.

    Set is_preferred=true to prioritize or is_blocked=true to exclude.
    """
    service = ReleaseGroupService(db)
    group = await service.set_preference(
        group_name,
        is_preferred=body.is_preferred,
        is_blocked=body.is_blocked,
        priority=body.priority,
        notes=body.notes,
    )
    await db.commit()

    if not group:
        raise HTTPException(status_code=404, detail="Release group not found")

    return {
        "id": group.id,
        "group_name": group.group_name,
        "is_preferred": group.is_preferred,
        "is_blocked": group.is_blocked,
        "priority": group.priority,
        "notes": group.notes,
    }

"""
Downloads API Endpoints
Approval workflow for torrent downloads
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.download_history import DownloadHistory
from app.models.pending_download import PendingDownload
from app.schemas.download import (
    DownloadApprovalRequest,
    DownloadHistoryListResponse,
    DownloadStats,
    PendingDownloadListResponse,
)
from app.services.download_service import DownloadActionError, process_download_action

router = APIRouter()
logger = get_logger(__name__)


@router.get("/pending", response_model=PendingDownloadListResponse)
async def get_pending_downloads(db: AsyncSession = Depends(get_db)):
    """
    Get all pending download approval requests

    Returns list of torrents awaiting user approval via Telegram.
    Includes expired requests for reference.
    """
    result = await db.execute(
        select(PendingDownload).order_by(PendingDownload.created_at.desc())
    )
    downloads = result.scalars().all()

    total = len(downloads)
    pending = sum(1 for d in downloads if d.is_pending)
    expired = sum(1 for d in downloads if d.is_expired)

    return PendingDownloadListResponse(
        total=total,
        pending=pending,
        expired=expired,
        downloads=downloads,
    )


@router.get("/pending/{download_id}")
async def get_pending_download(
    download_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific pending download by ID"""
    result = await db.execute(
        select(PendingDownload).where(PendingDownload.id == download_id)
    )
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    return download


@router.post("/pending/{download_id}/action")
async def approve_or_decline_download(
    download_id: int,
    request: DownloadApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve or decline a pending download

    Actions:
    - approve: Start download via qBittorrent
    - decline: Reject download with optional reason
    """
    try:
        download = await process_download_action(
            db=db,
            download_id=download_id,
            action=request.action,
            actor=request.approved_by,
            reason=request.reason,
        )
        return download
    except DownloadActionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/history", response_model=DownloadHistoryListResponse)
async def get_download_history(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """
    Get download history with pagination

    Returns historical record of all download decisions.
    """
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="page_size must be 1-100")

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(DownloadHistory)
    )
    total = count_result.scalar() or 0

    # Get records
    offset = (page - 1) * page_size
    result = await db.execute(
        select(DownloadHistory)
        .order_by(DownloadHistory.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    history = result.scalars().all()

    return DownloadHistoryListResponse(
        total=total,
        page=page,
        page_size=page_size,
        history=history,
    )


@router.get("/stats", response_model=DownloadStats)
async def get_download_stats(db: AsyncSession = Depends(get_db)):
    """
    Get download statistics

    Returns aggregate statistics about downloads:
    - Total downloads
    - Approved/declined/expired/pending counts
    - Success rate
    - Upgrade type breakdown
    """
    # Total downloads
    total_result = await db.execute(
        select(func.count()).select_from(DownloadHistory)
    )
    total = total_result.scalar() or 0

    # Count by action
    approved_result = await db.execute(
        select(func.count())
        .select_from(DownloadHistory)
        .where(DownloadHistory.action == "approved")
    )
    approved = approved_result.scalar() or 0

    declined_result = await db.execute(
        select(func.count())
        .select_from(DownloadHistory)
        .where(DownloadHistory.action == "declined")
    )
    declined = declined_result.scalar() or 0

    expired_result = await db.execute(
        select(func.count())
        .select_from(DownloadHistory)
        .where(DownloadHistory.action == "expired")
    )
    expired = expired_result.scalar() or 0

    # Pending downloads
    pending_result = await db.execute(
        select(func.count())
        .select_from(PendingDownload)
        .where(PendingDownload.status == "pending")
    )
    pending = pending_result.scalar() or 0

    # Success rate
    success_rate = (approved / total * 100) if total > 0 else 0.0

    # Upgrade count
    upgrades_result = await db.execute(
        select(func.count())
        .select_from(PendingDownload)
        .where(PendingDownload.is_upgrade == True)
    )
    upgrades = upgrades_result.scalar() or 0

    # Duplicates count
    duplicates_result = await db.execute(
        select(func.count())
        .select_from(PendingDownload)
        .where(PendingDownload.is_duplicate == True)
    )
    duplicates = duplicates_result.scalar() or 0

    # Upgrade type breakdown
    upgrade_type_result = await db.execute(
        select(DownloadHistory.upgrade_type, func.count(DownloadHistory.id))
        .where(DownloadHistory.upgrade_type.isnot(None))
        .group_by(DownloadHistory.upgrade_type)
    )
    by_upgrade_type = {
        upgrade_type: count for upgrade_type, count in upgrade_type_result.fetchall()
    }

    return DownloadStats(
        total_downloads=total,
        approved=approved,
        declined=declined,
        expired=expired,
        pending=pending,
        success_rate=success_rate,
        upgrades_found=upgrades,
        duplicates_found=duplicates,
        by_upgrade_type=by_upgrade_type,
    )

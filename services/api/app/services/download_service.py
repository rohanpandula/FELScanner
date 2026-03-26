"""
Download Service
Shared approval/decline logic for REST API and Telegram callback handler
"""
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.download_history import DownloadHistory
from app.models.pending_download import PendingDownload

logger = get_logger(__name__)


class DownloadActionError(Exception):
    """Raised when a download action cannot be completed"""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def process_download_action(
    db: AsyncSession,
    download_id: int,
    action: str,
    actor: str | None = None,
    reason: str | None = None,
) -> PendingDownload:
    """
    Process a download approval or decline action.

    Handles status update, history record creation, and qBittorrent trigger.
    Used by both the REST API endpoint and the Telegram callback handler.

    Args:
        db: Database session
        download_id: PendingDownload ID
        action: "approve" or "decline"
        actor: Username who performed the action
        reason: Optional reason for the action

    Returns:
        Updated PendingDownload record

    Raises:
        DownloadActionError: If download not found, not pending, or invalid action
    """
    result = await db.execute(
        select(PendingDownload).where(PendingDownload.id == download_id)
    )
    download = result.scalar_one_or_none()

    if not download:
        raise DownloadActionError("Download not found", status_code=404)

    if not download.is_pending:
        raise DownloadActionError("Download is not pending", status_code=400)

    if action == "approve":
        download.status = "approved"
        download.approved_by = actor
        download.approved_at = func.now()

        # Create history record
        history = DownloadHistory(
            torrent_id=download.torrent_id,
            torrent_name=download.torrent_name,
            movie_title=download.movie_title,
            movie_year=download.movie_year,
            movie_rating_key=download.movie_rating_key,
            action="approved",
            action_by=actor,
            action_reason=reason,
            quality=download.quality,
            upgrade_type=download.upgrade_type,
        )

        # Trigger qBittorrent download
        qbit_result = await _trigger_qbittorrent(download.torrent_url)
        if qbit_result["triggered"]:
            history.download_started_at = datetime.now()
            history.extra_data = {"download_triggered": True}
        elif qbit_result.get("error"):
            history.extra_data = {"qbittorrent_error": qbit_result["error"]}

        db.add(history)

    elif action == "decline":
        download.status = "declined"
        download.declined_reason = reason

        history = DownloadHistory(
            torrent_id=download.torrent_id,
            torrent_name=download.torrent_name,
            movie_title=download.movie_title,
            movie_year=download.movie_year,
            movie_rating_key=download.movie_rating_key,
            action="declined",
            action_by=actor,
            action_reason=reason,
            quality=download.quality,
            upgrade_type=download.upgrade_type,
        )
        db.add(history)

    else:
        raise DownloadActionError("Invalid action", status_code=400)

    await db.commit()
    await db.refresh(download)

    logger.info(
        "download.action_taken",
        download_id=download_id,
        action=action,
        by=actor,
    )

    return download


async def _trigger_qbittorrent(torrent_url: str) -> dict[str, Any]:
    """
    Trigger a qBittorrent download if configured.

    Non-blocking: failures are logged but don't prevent approval.

    Args:
        torrent_url: URL to the torrent file

    Returns:
        dict with "triggered" (bool) and optional "error" (str)
    """
    settings = get_settings()

    if not settings.QBITTORRENT_HOST:
        logger.info("download.qbittorrent_not_configured")
        return {"triggered": False}

    from app.integrations.qbittorrent.client import QBittorrentClient

    qbit = QBittorrentClient()
    try:
        success = await qbit.add_torrent(torrent_url)
        if success:
            logger.info("download.qbittorrent_triggered", url=torrent_url)
            return {"triggered": True}
        else:
            logger.error("download.qbittorrent_add_failed", url=torrent_url)
            return {"triggered": False, "error": "add_torrent returned False"}
    except Exception as e:
        logger.error("download.qbittorrent_error", url=torrent_url, error=str(e))
        return {"triggered": False, "error": str(e)}
    finally:
        await qbit.close()

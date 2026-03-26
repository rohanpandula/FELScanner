"""
Activity Service
Manages the chronological activity feed
"""
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.activity_log import ActivityLog

logger = get_logger(__name__)


class ActivityService:
    """Activity feed management and querying"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_event(
        self,
        event_type: str,
        title: str,
        description: str | None = None,
        severity: str = "info",
        movie_id: int | None = None,
        movie_title: str | None = None,
        movie_year: int | None = None,
        related_id: str | None = None,
        related_type: str | None = None,
        quality_before: str | None = None,
        quality_after: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ActivityLog:
        """Create a new activity log entry"""
        entry = ActivityLog(
            event_type=event_type,
            title=title,
            description=description,
            severity=severity,
            movie_id=movie_id,
            movie_title=movie_title,
            movie_year=movie_year,
            related_id=related_id,
            related_type=related_type,
            quality_before=quality_before,
            quality_after=quality_after,
            metadata=metadata,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_feed(
        self,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
        severity: str | None = None,
        movie_id: int | None = None,
    ) -> tuple[list[ActivityLog], int]:
        """
        Get paginated activity feed.

        Returns (events, total_count).
        """
        query = select(ActivityLog)

        if event_type:
            query = query.where(ActivityLog.event_type == event_type)
        if severity:
            query = query.where(ActivityLog.severity == severity)
        if movie_id:
            query = query.where(ActivityLog.movie_id == movie_id)

        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Fetch results
        query = query.order_by(ActivityLog.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        events = result.scalars().all()

        return events, total

    async def get_movie_timeline(self, movie_id: int) -> list[ActivityLog]:
        """Get all activity for a specific movie"""
        result = await self.db.execute(
            select(ActivityLog)
            .where(ActivityLog.movie_id == movie_id)
            .order_by(ActivityLog.created_at.desc())
        )
        return result.scalars().all()

    async def get_event_type_counts(self) -> dict[str, int]:
        """Get count of events by type"""
        result = await self.db.execute(
            select(ActivityLog.event_type, func.count(ActivityLog.id))
            .group_by(ActivityLog.event_type)
        )
        return {event_type: count for event_type, count in result.fetchall()}

    async def get_recent_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get summary of activity in the last N hours"""
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = select(ActivityLog).where(ActivityLog.created_at >= cutoff)
        result = await self.db.execute(query)
        events = result.scalars().all()

        type_counts: dict[str, int] = {}
        severity_counts: dict[str, int] = {}
        for event in events:
            type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1
            severity_counts[event.severity] = severity_counts.get(event.severity, 0) + 1

        return {
            "total_events": len(events),
            "hours": hours,
            "by_type": type_counts,
            "by_severity": severity_counts,
        }

    # ------------------------------------------------------------------
    # Convenience methods for common events
    # ------------------------------------------------------------------

    async def log_movie_added(
        self, movie_id: int, title: str, year: int | None, quality: str
    ) -> ActivityLog:
        return await self.log_event(
            event_type="movie_added",
            title=f"Added {title}",
            description=f"{quality}",
            severity="success",
            movie_id=movie_id,
            movie_title=title,
            movie_year=year,
            quality_after=quality,
        )

    async def log_movie_upgraded(
        self,
        movie_id: int,
        title: str,
        year: int | None,
        quality_before: str,
        quality_after: str,
    ) -> ActivityLog:
        return await self.log_event(
            event_type="movie_upgraded",
            title=f"Upgraded {title}",
            description=f"{quality_before} → {quality_after}",
            severity="success",
            movie_id=movie_id,
            movie_title=title,
            movie_year=year,
            quality_before=quality_before,
            quality_after=quality_after,
        )

    async def log_download_approved(
        self,
        movie_title: str,
        torrent_name: str,
        quality: str,
        movie_id: int | None = None,
    ) -> ActivityLog:
        return await self.log_event(
            event_type="download_approved",
            title=f"Approved download for {movie_title}",
            description=f"{torrent_name} ({quality})",
            severity="success",
            movie_id=movie_id,
            movie_title=movie_title,
        )

    async def log_download_declined(
        self,
        movie_title: str,
        reason: str | None = None,
        movie_id: int | None = None,
    ) -> ActivityLog:
        return await self.log_event(
            event_type="download_declined",
            title=f"Declined download for {movie_title}",
            description=reason,
            severity="info",
            movie_id=movie_id,
            movie_title=movie_title,
        )

    async def log_scan_completed(
        self,
        scan_type: str,
        total_movies: int,
        changes: int,
        duration_seconds: int | None = None,
        scan_id: int | None = None,
    ) -> ActivityLog:
        return await self.log_event(
            event_type="scan_completed",
            title=f"{scan_type.capitalize()} scan completed",
            description=f"{total_movies} movies scanned, {changes} changes detected",
            severity="info",
            related_id=str(scan_id) if scan_id else None,
            related_type="scan",
            metadata={
                "total_movies": total_movies,
                "changes": changes,
                "duration_seconds": duration_seconds,
            },
        )

    async def log_ipt_scan(
        self, total_torrents: int, new_torrents: int
    ) -> ActivityLog:
        return await self.log_event(
            event_type="ipt_scan",
            title=f"IPT scan found {new_torrents} new torrents",
            description=f"{total_torrents} total results",
            severity="info" if new_torrents == 0 else "success",
            metadata={
                "total": total_torrents,
                "new": new_torrents,
            },
        )

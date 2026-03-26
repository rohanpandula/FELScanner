"""
Release Group Service
Track release group reputation, preferences, and statistics
"""
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.release_group_preference import ReleaseGroupPreference

logger = get_logger(__name__)


class ReleaseGroupService:
    """Release group reputation tracking and preference management"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_groups(
        self,
        sort_by: str = "total_releases_seen",
        sort_order: str = "desc",
        preferred_only: bool = False,
    ) -> list[ReleaseGroupPreference]:
        """Get all known release groups with stats"""
        query = select(ReleaseGroupPreference)

        if preferred_only:
            query = query.where(ReleaseGroupPreference.is_preferred == True)

        sort_field = getattr(
            ReleaseGroupPreference, sort_by, ReleaseGroupPreference.total_releases_seen
        )
        if sort_order == "desc":
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_group(self, group_name: str) -> ReleaseGroupPreference | None:
        """Get a specific release group by name"""
        result = await self.db.execute(
            select(ReleaseGroupPreference).where(
                ReleaseGroupPreference.group_name == group_name
            )
        )
        return result.scalar_one_or_none()

    async def upsert_group(
        self,
        group_name: str,
        quality_score: float | None = None,
        file_size_gb: float | None = None,
    ) -> ReleaseGroupPreference:
        """
        Create or update a release group entry.
        Called automatically when IPT results are enriched.
        """
        existing = await self.get_group(group_name)

        if existing:
            existing.total_releases_seen += 1
            existing.last_seen_at = func.now()

            # Rolling average for quality score
            if quality_score is not None and existing.avg_quality_score is not None:
                n = existing.total_releases_seen
                existing.avg_quality_score = (
                    (float(existing.avg_quality_score) * (n - 1) + quality_score) / n
                )
            elif quality_score is not None:
                existing.avg_quality_score = quality_score

            # Rolling average for file size
            if file_size_gb is not None and existing.avg_file_size_gb is not None:
                n = existing.total_releases_seen
                existing.avg_file_size_gb = (
                    (float(existing.avg_file_size_gb) * (n - 1) + file_size_gb) / n
                )
            elif file_size_gb is not None:
                existing.avg_file_size_gb = file_size_gb

            await self.db.flush()
            return existing
        else:
            group = ReleaseGroupPreference(
                group_name=group_name,
                total_releases_seen=1,
                avg_quality_score=quality_score,
                avg_file_size_gb=file_size_gb,
            )
            self.db.add(group)
            await self.db.flush()
            return group

    async def set_preference(
        self,
        group_name: str,
        is_preferred: bool | None = None,
        is_blocked: bool | None = None,
        priority: int | None = None,
        notes: str | None = None,
    ) -> ReleaseGroupPreference | None:
        """Set user preference for a release group"""
        group = await self.get_group(group_name)
        if not group:
            group = ReleaseGroupPreference(group_name=group_name)
            self.db.add(group)

        if is_preferred is not None:
            group.is_preferred = is_preferred
            if is_preferred:
                group.is_blocked = False
        if is_blocked is not None:
            group.is_blocked = is_blocked
            if is_blocked:
                group.is_preferred = False
        if priority is not None:
            group.priority = priority
        if notes is not None:
            group.notes = notes

        await self.db.flush()
        return group

    async def get_preferred_groups(self) -> list[str]:
        """Get list of preferred group names"""
        result = await self.db.execute(
            select(ReleaseGroupPreference.group_name)
            .where(ReleaseGroupPreference.is_preferred == True)
            .order_by(ReleaseGroupPreference.priority.desc())
        )
        return [r for r in result.scalars().all()]

    async def get_blocked_groups(self) -> list[str]:
        """Get list of blocked group names"""
        result = await self.db.execute(
            select(ReleaseGroupPreference.group_name)
            .where(ReleaseGroupPreference.is_blocked == True)
        )
        return [r for r in result.scalars().all()]

    async def get_group_stats_summary(self) -> dict[str, Any]:
        """Get summary stats across all known groups"""
        total_result = await self.db.execute(
            select(func.count()).select_from(ReleaseGroupPreference)
        )
        total = total_result.scalar() or 0

        preferred_result = await self.db.execute(
            select(func.count())
            .select_from(ReleaseGroupPreference)
            .where(ReleaseGroupPreference.is_preferred == True)
        )
        preferred = preferred_result.scalar() or 0

        blocked_result = await self.db.execute(
            select(func.count())
            .select_from(ReleaseGroupPreference)
            .where(ReleaseGroupPreference.is_blocked == True)
        )
        blocked = blocked_result.scalar() or 0

        # Top 5 by releases seen
        top_result = await self.db.execute(
            select(
                ReleaseGroupPreference.group_name,
                ReleaseGroupPreference.total_releases_seen,
                ReleaseGroupPreference.avg_quality_score,
                ReleaseGroupPreference.avg_file_size_gb,
                ReleaseGroupPreference.is_preferred,
            )
            .order_by(ReleaseGroupPreference.total_releases_seen.desc())
            .limit(5)
        )
        top_groups = [
            {
                "group_name": name,
                "releases_seen": seen,
                "avg_quality": float(qs) if qs else None,
                "avg_size_gb": float(sz) if sz else None,
                "is_preferred": pref,
            }
            for name, seen, qs, sz, pref in top_result.fetchall()
        ]

        return {
            "total_groups": total,
            "preferred_count": preferred,
            "blocked_count": blocked,
            "top_groups": top_groups,
        }

    async def bulk_update_from_torrents(
        self, torrents: list[dict[str, Any]]
    ) -> int:
        """
        Bulk update release group stats from a list of enriched torrents.
        Called after IPT scan enrichment.
        """
        updated = 0
        for torrent in torrents:
            metadata = torrent.get("metadata", {})
            group_name = metadata.get("release_group")
            if not group_name:
                continue

            quality_score = metadata.get("quality_score")

            # Try to parse file size to GB
            file_size_gb = None
            size_str = torrent.get("size", "")
            if size_str:
                try:
                    if "GB" in size_str.upper():
                        file_size_gb = float(size_str.upper().replace("GB", "").strip())
                    elif "MB" in size_str.upper():
                        file_size_gb = float(size_str.upper().replace("MB", "").strip()) / 1024
                except (ValueError, TypeError):
                    pass

            await self.upsert_group(group_name, quality_score, file_size_gb)
            updated += 1

        await self.db.commit()
        return updated

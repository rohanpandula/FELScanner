"""
Scan Service
Orchestrates library scanning with Dolby Vision detection
"""
import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.plex.collection_manager import CollectionManager
from app.integrations.plex.scanner import PlexScanner
from app.models.movie import Movie
from app.models.scan_history import ScanHistory

logger = get_logger(__name__)


class ScanService:
    """
    Library scanning orchestration service

    Manages the complete scan workflow:
    1. Fetch movies from Plex
    2. Analyze each movie for DV profile, FEL, Atmos
    3. Update database
    4. Update Plex collections
    5. Track scan history
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize scan service

        Args:
            db: Database session
        """
        self.db = db
        self.scanner = PlexScanner()
        self.collection_manager = CollectionManager()
        self._scan_lock = asyncio.Lock()
        self._current_scan: ScanHistory | None = None

    async def is_scan_running(self) -> bool:
        """Check if a scan is currently running"""
        return self._scan_lock.locked()

    async def get_current_scan(self) -> ScanHistory | None:
        """Get current scan record if one is running"""
        return self._current_scan

    async def trigger_full_scan(
        self,
        trigger: str = "manual",
        triggered_by: str | None = None,
        on_progress: callable = None,
    ) -> ScanHistory:
        """
        Trigger a full library scan

        Args:
            trigger: What triggered the scan (manual, scheduled, webhook)
            triggered_by: User or system that initiated
            on_progress: Optional callback for streaming progress updates

        Returns:
            ScanHistory: Scan record

        Raises:
            RuntimeError: If a scan is already running
        """
        if self._scan_lock.locked():
            raise RuntimeError("A scan is already in progress")

        async with self._scan_lock:
            # Create scan history record
            scan_record = ScanHistory(
                scan_type="full",
                trigger=trigger,
                triggered_by=triggered_by,
                status="running",
            )
            self.db.add(scan_record)
            await self.db.commit()
            await self.db.refresh(scan_record)

            self._current_scan = scan_record

            logger.info(
                "scan.started",
                scan_id=scan_record.id,
                trigger=trigger,
                triggered_by=triggered_by,
            )

            try:
                # Connect to Plex
                await self.scanner.client.connect()

                if on_progress:
                    on_progress("Starting library scan...", 0, 0, None)

                # Scan all movies with progress callback
                scanned_movies = await self.scanner.scan_library(
                    on_progress=on_progress
                )

                logger.info("scan.movies_scanned", count=len(scanned_movies))

                if on_progress:
                    on_progress("Updating database...", 0, 0, None)

                # Update database
                stats = await self._update_database(scanned_movies)

                if on_progress:
                    on_progress("Updating Plex collections...", 0, 0, None)

                # Update collections
                collection_stats = await self._update_collections(scanned_movies)

                # Update scan record with results
                scan_record.status = "completed"
                scan_record.completed_at = datetime.now()
                scan_record.movies_scanned = len(scanned_movies)
                scan_record.movies_added = stats["added"]
                scan_record.movies_updated = stats["updated"]
                scan_record.movies_removed = stats["removed"]
                scan_record.dv_discovered = stats["dv_count"]
                scan_record.fel_discovered = stats["fel_count"]
                scan_record.atmos_discovered = stats["atmos_count"]
                scan_record.collections_updated = sum(collection_stats.values())
                scan_record.extra_data = {
                    "collection_stats": collection_stats,
                }

                # Calculate duration
                duration = (scan_record.completed_at - scan_record.started_at).total_seconds()
                scan_record.duration_seconds = duration

                await self.db.commit()
                await self.db.refresh(scan_record)

                logger.info(
                    "scan.completed",
                    scan_id=scan_record.id,
                    duration_seconds=duration,
                    movies_scanned=scan_record.movies_scanned,
                    dv_discovered=scan_record.dv_discovered,
                    fel_discovered=scan_record.fel_discovered,
                )

                return scan_record

            except Exception as e:
                logger.error("scan.failed", error=str(e), exc_info=True)

                # Update scan record with error
                scan_record.status = "failed"
                scan_record.error_message = str(e)
                scan_record.completed_at = datetime.now()
                await self.db.commit()

                raise

            finally:
                self._current_scan = None
                await self.scanner.close()

    async def _update_database(
        self, scanned_movies: list[dict[str, Any]]
    ) -> dict[str, int]:
        """
        Update database with scanned movie data

        Args:
            scanned_movies: List of scanned movie metadata

        Returns:
            dict: Statistics (added, updated, removed, dv_count, fel_count, atmos_count)
        """
        stats = {
            "added": 0,
            "updated": 0,
            "removed": 0,
            "dv_count": 0,
            "fel_count": 0,
            "atmos_count": 0,
        }

        # Deduplicate scanned movies by rating_key (keep last occurrence)
        seen_keys: dict[str, dict] = {}
        for m in scanned_movies:
            seen_keys[m["rating_key"]] = m
        scanned_movies = list(seen_keys.values())

        # Build set of scanned keys first
        scanned_rating_keys = {m["rating_key"] for m in scanned_movies}

        # Lightweight query for all existing keys (for removal detection)
        result = await self.db.execute(select(Movie.rating_key))
        all_existing_keys = {row[0] for row in result.fetchall()}

        # Load full objects only for movies we need to update
        keys_to_update = scanned_rating_keys & all_existing_keys
        if keys_to_update:
            result = await self.db.execute(
                select(Movie).where(Movie.rating_key.in_(keys_to_update))
            )
            existing_movies = {m.rating_key: m for m in result.scalars().all()}
        else:
            existing_movies = {}

        # Process scanned movies
        for movie_data in scanned_movies:
            rating_key = movie_data["rating_key"]

            # Count discoveries
            if movie_data.get("dv_profile"):
                stats["dv_count"] += 1
            if movie_data.get("dv_fel"):
                stats["fel_count"] += 1
            if movie_data.get("has_atmos"):
                stats["atmos_count"] += 1

            if rating_key in existing_movies:
                # Update existing movie
                movie = existing_movies[rating_key]
                for key, value in movie_data.items():
                    if key not in ("rating_key", "id", "created_at", "updated_at"):
                        setattr(movie, key, value)
                movie.last_scanned_at = datetime.now()
                # Set collection flags inline (avoids re-query in _update_collections)
                movie.in_dv_collection = movie_data.get("dv_profile") is not None
                movie.in_p7_collection = movie_data.get("dv_fel", False)
                movie.in_atmos_collection = movie_data.get("has_atmos", False)
                stats["updated"] += 1

            else:
                # Add new movie (use merge to handle duplicate rating_keys)
                movie = Movie(**movie_data)
                movie.last_scanned_at = datetime.now()
                movie.in_dv_collection = movie_data.get("dv_profile") is not None
                movie.in_p7_collection = movie_data.get("dv_fel", False)
                movie.in_atmos_collection = movie_data.get("has_atmos", False)
                self.db.add(movie)
                stats["added"] += 1

        # Mark movies no longer in Plex as stale
        removed_rating_keys = all_existing_keys - scanned_rating_keys
        if removed_rating_keys:
            await self.db.execute(
                update(Movie)
                .where(Movie.rating_key.in_(removed_rating_keys))
                .values(last_scanned_at=datetime.now())
            )
            stats["removed"] = len(removed_rating_keys)

        await self.db.commit()

        logger.info(
            "scan.database_updated",
            added=stats["added"],
            updated=stats["updated"],
            removed=stats["removed"],
        )

        return stats

    async def _update_collections(
        self, scanned_movies: list[dict[str, Any]]
    ) -> dict[str, int]:
        """
        Update Plex collections for all movies.

        Collection flags are already set in _update_database, so this method
        only needs to verify the actual Plex collections match the DB state.

        Args:
            scanned_movies: List of scanned movie metadata

        Returns:
            dict: Collection update statistics
        """
        # Collection flags already set in _update_database —
        # just pass movie data to collection manager for Plex-side verification
        collection_stats = await self.collection_manager.verify_collections(
            scanned_movies
        )

        logger.info("scan.collections_updated", stats=collection_stats)

        return collection_stats

    async def get_scan_history(
        self, limit: int = 10, offset: int = 0
    ) -> tuple[list[ScanHistory], int]:
        """
        Get scan history with pagination

        Args:
            limit: Number of records to return
            offset: Offset for pagination

        Returns:
            tuple: (scan_records, total_count)
        """
        # Get total count
        count_result = await self.db.execute(
            select(func.count()).select_from(ScanHistory)
        )
        total = count_result.scalar() or 0

        # Get records
        result = await self.db.execute(
            select(ScanHistory)
            .order_by(ScanHistory.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        scans = result.scalars().all()

        return scans, total

    async def get_scan_by_id(self, scan_id: int) -> ScanHistory | None:
        """
        Get a specific scan record

        Args:
            scan_id: Scan ID

        Returns:
            ScanHistory or None
        """
        result = await self.db.execute(
            select(ScanHistory).where(ScanHistory.id == scan_id)
        )
        return result.scalar_one_or_none()

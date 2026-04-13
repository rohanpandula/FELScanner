"""
Plex Collection Manager
Manages Plex collections for DV, P7 FEL, and Atmos movies
"""
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.plex.client import PlexClient

logger = get_logger(__name__)


class CollectionManager:
    """
    Plex collection management

    Handles automatic collection updates for:
    - All Dolby Vision
    - DV Profile 7 FEL
    - TrueHD Atmos
    """

    def __init__(self):
        """Initialize collection manager"""
        self.settings = get_settings()
        self.client = PlexClient()

    async def add_to_dv_collection(self, rating_key: str, movie_title: str) -> bool:
        """
        Add movie to "All Dolby Vision" collection

        Args:
            rating_key: Plex rating key
            movie_title: Movie title (for logging)

        Returns:
            bool: True if successful
        """
        if not self.settings.COLLECTION_ENABLE_DV:
            logger.debug("collection.dv_disabled")
            return False

        collection_name = self.settings.COLLECTION_NAME_ALL_DV
        success = await self.client.add_to_collection(collection_name, rating_key)

        if success:
            logger.info(
                "collection.added_to_dv",
                movie=movie_title,
                rating_key=rating_key,
                collection=collection_name,
            )

        return success

    async def add_to_p7_collection(self, rating_key: str, movie_title: str) -> bool:
        """
        Add movie to "DV FEL Profile 7" collection

        Args:
            rating_key: Plex rating key
            movie_title: Movie title (for logging)

        Returns:
            bool: True if successful
        """
        if not self.settings.COLLECTION_ENABLE_P7:
            logger.debug("collection.p7_disabled")
            return False

        collection_name = self.settings.COLLECTION_NAME_PROFILE7
        success = await self.client.add_to_collection(collection_name, rating_key)

        if success:
            logger.info(
                "collection.added_to_p7",
                movie=movie_title,
                rating_key=rating_key,
                collection=collection_name,
            )

        return success

    async def add_to_atmos_collection(self, rating_key: str, movie_title: str) -> bool:
        """
        Add movie to "TrueHD Atmos" collection

        Args:
            rating_key: Plex rating key
            movie_title: Movie title (for logging)

        Returns:
            bool: True if successful
        """
        if not self.settings.COLLECTION_ENABLE_ATMOS:
            logger.debug("collection.atmos_disabled")
            return False

        collection_name = self.settings.COLLECTION_NAME_TRUEHD_ATMOS
        success = await self.client.add_to_collection(collection_name, rating_key)

        if success:
            logger.info(
                "collection.added_to_atmos",
                movie=movie_title,
                rating_key=rating_key,
                collection=collection_name,
            )

        return success

    async def remove_from_dv_collection(self, rating_key: str, movie_title: str) -> bool:
        """Remove movie from DV collection"""
        if not self.settings.COLLECTION_ENABLE_DV:
            return False

        collection_name = self.settings.COLLECTION_NAME_ALL_DV
        return await self.client.remove_from_collection(collection_name, rating_key)

    async def remove_from_p7_collection(self, rating_key: str, movie_title: str) -> bool:
        """Remove movie from P7 collection"""
        if not self.settings.COLLECTION_ENABLE_P7:
            return False

        collection_name = self.settings.COLLECTION_NAME_PROFILE7
        return await self.client.remove_from_collection(collection_name, rating_key)

    async def remove_from_atmos_collection(self, rating_key: str, movie_title: str) -> bool:
        """Remove movie from Atmos collection"""
        if not self.settings.COLLECTION_ENABLE_ATMOS:
            return False

        collection_name = self.settings.COLLECTION_NAME_TRUEHD_ATMOS
        return await self.client.remove_from_collection(collection_name, rating_key)

    async def update_collections_for_movie(
        self, movie_data: dict[str, Any]
    ) -> dict[str, bool]:
        """
        Update all collections for a movie based on its metadata

        Args:
            movie_data: Movie metadata from scanner

        Returns:
            dict: Collection update results
                {
                    "in_dv_collection": bool,
                    "in_p7_collection": bool,
                    "in_atmos_collection": bool
                }
        """
        rating_key = movie_data["rating_key"]
        title = movie_data["title"]
        dv_profile = movie_data.get("dv_profile")
        dv_fel = movie_data.get("dv_fel", False)
        has_atmos = movie_data.get("has_atmos", False)

        results = {
            "in_dv_collection": False,
            "in_p7_collection": False,
            "in_atmos_collection": False,
        }

        # Add to DV collection if has any DV profile
        if dv_profile and self.settings.COLLECTION_ENABLE_DV:
            results["in_dv_collection"] = await self.add_to_dv_collection(
                rating_key, title
            )

        # Add to P7 collection if has FEL
        if dv_fel and self.settings.COLLECTION_ENABLE_P7:
            results["in_p7_collection"] = await self.add_to_p7_collection(
                rating_key, title
            )

        # Add to Atmos collection if has Atmos
        if has_atmos and self.settings.COLLECTION_ENABLE_ATMOS:
            results["in_atmos_collection"] = await self.add_to_atmos_collection(
                rating_key, title
            )

        return results

    async def verify_collections(
        self, movies: list[dict[str, Any]], on_progress=None
    ) -> dict[str, int]:
        """
        Verify all movies are in correct collections

        Removes movies that shouldn't be in collections and
        adds movies that are missing.

        Args:
            movies: List of all movie metadata
            on_progress: Optional callback(message, done, total, current) to
                stream status while the (potentially long) collection-update
                phase runs.

        Returns:
            dict: Statistics
                {
                    "dv_added": int,
                    "dv_removed": int,
                    "p7_added": int,
                    "p7_removed": int,
                    "atmos_added": int,
                    "atmos_removed": int
                }
        """
        stats = {
            "dv_added": 0,
            "dv_removed": 0,
            "p7_added": 0,
            "p7_removed": 0,
            "atmos_added": 0,
            "atmos_removed": 0,
        }

        total = len(movies)
        processed = 0
        last_emit = 0

        for movie in movies:
            rating_key = movie["rating_key"]
            title = movie["title"]
            dv_profile = movie.get("dv_profile")
            dv_fel = movie.get("dv_fel", False)
            has_atmos = movie.get("has_atmos", False)
            in_dv = movie.get("in_dv_collection", False)
            in_p7 = movie.get("in_p7_collection", False)
            in_atmos = movie.get("in_atmos_collection", False)

            # DV collection logic
            should_be_in_dv = dv_profile is not None
            if should_be_in_dv and not in_dv:
                if await self.add_to_dv_collection(rating_key, title):
                    stats["dv_added"] += 1
            elif not should_be_in_dv and in_dv:
                if await self.remove_from_dv_collection(rating_key, title):
                    stats["dv_removed"] += 1

            # P7 collection logic
            should_be_in_p7 = dv_fel
            if should_be_in_p7 and not in_p7:
                if await self.add_to_p7_collection(rating_key, title):
                    stats["p7_added"] += 1
            elif not should_be_in_p7 and in_p7:
                if await self.remove_from_p7_collection(rating_key, title):
                    stats["p7_removed"] += 1

            # Atmos collection logic
            should_be_in_atmos = has_atmos
            if should_be_in_atmos and not in_atmos:
                if await self.add_to_atmos_collection(rating_key, title):
                    stats["atmos_added"] += 1
            elif not should_be_in_atmos and in_atmos:
                if await self.remove_from_atmos_collection(rating_key, title):
                    stats["atmos_removed"] += 1

            processed += 1
            # Emit a log line every 50 movies so the UI never goes dark during
            # the collection-update phase.
            if on_progress and (processed - last_emit >= 50 or processed == total):
                on_progress(
                    f"Updating collections {processed}/{total} "
                    f"(+DV {stats['dv_added']}, +P7 {stats['p7_added']}, +Atmos {stats['atmos_added']})",
                    processed,
                    total,
                    title,
                )
                last_emit = processed

        logger.info("collection.verify_complete", stats=stats)
        return stats

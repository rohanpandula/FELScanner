"""
Plex API Client
Async wrapper around plexapi for core Plex operations
"""
import asyncio
from typing import Any

from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from plexapi.video import Movie as PlexMovie

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PlexClient:
    """
    Async Plex API client

    Provides async wrappers around plexapi (which is sync)
    for non-blocking Plex server operations.
    """

    def __init__(self):
        """Initialize Plex client with settings"""
        self.settings = get_settings()
        self._server: PlexServer | None = None
        self._library = None

    async def connect(self) -> bool:
        """
        Connect to Plex server and verify library

        Returns:
            bool: True if connected successfully
        """
        try:
            # Run sync plexapi calls in executor
            loop = asyncio.get_event_loop()
            self._server = await loop.run_in_executor(
                None,
                lambda: PlexServer(
                    self.settings.PLEX_URL,
                    self.settings.PLEX_TOKEN,
                    timeout=self.settings.PLEX_TIMEOUT,
                ),
            )

            # Get library
            self._library = await loop.run_in_executor(
                None, self._server.library.section, self.settings.LIBRARY_NAME
            )

            logger.info(
                "plex.connected",
                server_name=self._server.friendlyName,
                library=self.settings.LIBRARY_NAME,
                version=self._server.version,
            )
            return True

        except Exception as e:
            logger.error("plex.connection_failed", error=str(e))
            return False

    async def get_all_movies(self, chunk_size: int = 500) -> list[PlexMovie]:
        """
        Get all movies from the library using chunked fetching.

        Fetches movies in chunks to limit memory usage for large libraries.

        Args:
            chunk_size: Number of movies to fetch per chunk

        Returns:
            list[PlexMovie]: All movies in the library
        """
        if not self._library:
            await self.connect()

        loop = asyncio.get_event_loop()
        movies = []
        offset = 0

        while True:
            chunk = await loop.run_in_executor(
                None,
                lambda o=offset: self._library.all(
                    maxresults=chunk_size, container_start=o
                ),
            )
            movies.extend(chunk)
            if len(chunk) < chunk_size:
                break
            offset += chunk_size

        logger.info("plex.movies_fetched", count=len(movies))
        return movies

    async def get_movie_by_rating_key(self, rating_key: str) -> PlexMovie | None:
        """
        Get a specific movie by rating key

        Args:
            rating_key: Plex unique identifier

        Returns:
            PlexMovie or None if not found
        """
        if not self._server:
            await self.connect()

        try:
            loop = asyncio.get_event_loop()
            movie = await loop.run_in_executor(
                None, self._server.fetchItem, int(rating_key)
            )
            return movie
        except Exception as e:
            logger.warning("plex.movie_not_found", rating_key=rating_key, error=str(e))
            return None

    async def search_movie(self, title: str, year: int | None = None) -> list[PlexMovie]:
        """
        Search for movies by title and optional year

        Args:
            title: Movie title
            year: Release year (optional)

        Returns:
            list[PlexMovie]: Matching movies
        """
        if not self._library:
            await self.connect()

        loop = asyncio.get_event_loop()

        if year:
            results = await loop.run_in_executor(
                None, self._library.search, title, year=year
            )
        else:
            results = await loop.run_in_executor(
                None, self._library.search, title
            )

        logger.debug("plex.search", title=title, year=year, results=len(results))
        return results

    async def get_collection(self, collection_name: str) -> Any | None:
        """
        Get a Plex collection by name

        Args:
            collection_name: Name of the collection

        Returns:
            Collection object or None
        """
        if not self._library:
            await self.connect()

        try:
            loop = asyncio.get_event_loop()
            collections = await loop.run_in_executor(None, self._library.collections)

            for collection in collections:
                if collection.title == collection_name:
                    return collection

            logger.debug("plex.collection_not_found", name=collection_name)
            return None

        except Exception as e:
            logger.error("plex.collection_error", name=collection_name, error=str(e))
            return None

    async def create_collection(self, collection_name: str) -> Any:
        """
        Create a new Plex collection

        Args:
            collection_name: Name for the new collection

        Returns:
            Collection object
        """
        if not self._library:
            await self.connect()

        loop = asyncio.get_event_loop()
        collection = await loop.run_in_executor(
            None, self._library.createCollection, collection_name, []
        )

        logger.info("plex.collection_created", name=collection_name)
        return collection

    async def add_to_collection(self, collection_name: str, rating_key: str) -> bool:
        """
        Add a movie to a collection

        Args:
            collection_name: Collection name
            rating_key: Movie rating key

        Returns:
            bool: True if successful
        """
        try:
            collection = await self.get_collection(collection_name)

            if not collection:
                collection = await self.create_collection(collection_name)

            movie = await self.get_movie_by_rating_key(rating_key)
            if not movie:
                logger.warning("plex.movie_not_found_for_collection", rating_key=rating_key)
                return False

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, collection.addItems, [movie])

            logger.info(
                "plex.added_to_collection",
                collection=collection_name,
                rating_key=rating_key,
            )
            return True

        except Exception as e:
            logger.error(
                "plex.add_to_collection_failed",
                collection=collection_name,
                rating_key=rating_key,
                error=str(e),
            )
            return False

    async def remove_from_collection(self, collection_name: str, rating_key: str) -> bool:
        """
        Remove a movie from a collection

        Args:
            collection_name: Collection name
            rating_key: Movie rating key

        Returns:
            bool: True if successful
        """
        try:
            collection = await self.get_collection(collection_name)
            if not collection:
                logger.warning("plex.collection_not_found", name=collection_name)
                return False

            movie = await self.get_movie_by_rating_key(rating_key)
            if not movie:
                return False

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, collection.removeItems, [movie])

            logger.info(
                "plex.removed_from_collection",
                collection=collection_name,
                rating_key=rating_key,
            )
            return True

        except Exception as e:
            logger.error(
                "plex.remove_from_collection_failed",
                collection=collection_name,
                rating_key=rating_key,
                error=str(e),
            )
            return False

    async def get_server_info(self) -> dict[str, Any]:
        """
        Get Plex server information

        Returns:
            dict: Server metadata
        """
        if not self._server:
            await self.connect()

        return {
            "name": self._server.friendlyName,
            "version": self._server.version,
            "platform": self._server.platform,
            "platform_version": self._server.platformVersion,
            "library_name": self.settings.LIBRARY_NAME,
        }

    async def refresh_library(self) -> bool:
        """
        Trigger a library refresh in Plex

        Returns:
            bool: True if refresh triggered
        """
        try:
            if not self._library:
                await self.connect()

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._library.update)

            logger.info("plex.library_refresh_triggered")
            return True

        except Exception as e:
            logger.error("plex.library_refresh_failed", error=str(e))
            return False

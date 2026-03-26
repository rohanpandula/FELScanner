"""
Radarr Client
Async client for Radarr API
"""
from typing import Any
from urllib.parse import urljoin

import aiohttp

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RadarrClient:
    """
    Async Radarr API client

    Handles movie lookups, download folder path resolution,
    and quality profile queries.
    """

    def __init__(self):
        """Initialize Radarr client"""
        self.settings = get_settings()
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.settings.RADARR_TIMEOUT)
            )
        return self._session

    async def close(self):
        """Close aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> dict[str, Any] | list[Any] | None:
        """
        Make authenticated request to Radarr API

        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., "/api/v3/movie")
            **kwargs: Additional request parameters

        Returns:
            Response data or None if failed
        """
        if not self.settings.RADARR_URL or not self.settings.RADARR_API_KEY:
            logger.warning("radarr.not_configured")
            return None

        url = urljoin(self.settings.RADARR_URL, endpoint)

        # Add API key header
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        kwargs["headers"]["X-Api-Key"] = self.settings.RADARR_API_KEY

        try:
            session = await self._get_session()
            async with session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(
                        "radarr.request_failed",
                        endpoint=endpoint,
                        status=response.status,
                    )
                    return None

        except Exception as e:
            logger.error("radarr.request_error", endpoint=endpoint, error=str(e))
            return None

    async def search_movie(
        self, title: str, year: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Search for a movie by title and year

        Args:
            title: Movie title
            year: Release year (optional)

        Returns:
            list: Matching movies from Radarr
        """
        params = {"term": title}

        result = await self._request("GET", "/api/v3/movie/lookup", params=params)

        if not isinstance(result, list):
            return []

        # Filter by year if provided
        if year:
            result = [m for m in result if m.get("year") == year]

        logger.debug("radarr.search_movie", title=title, year=year, results=len(result))
        return result

    async def get_movie_by_id(self, radarr_id: int) -> dict[str, Any] | None:
        """
        Get movie details by Radarr ID

        Args:
            radarr_id: Radarr movie ID

        Returns:
            dict: Movie details or None
        """
        result = await self._request("GET", f"/api/v3/movie/{radarr_id}")

        if isinstance(result, dict):
            return result
        else:
            return None

    async def get_all_movies(self) -> list[dict[str, Any]]:
        """
        Get all movies in Radarr library

        Returns:
            list: All movies
        """
        result = await self._request("GET", "/api/v3/movie")

        if isinstance(result, list):
            return result
        else:
            return []

    async def get_movie_folder_path(
        self, title: str, year: int | None = None
    ) -> str | None:
        """
        Get the folder path for a movie

        Useful for version stacking in Plex when using Radarr-managed folders.

        Args:
            title: Movie title
            year: Release year

        Returns:
            str: Folder path or None if not found
        """
        movies = await self.search_movie(title, year)

        if not movies:
            # Try searching all movies
            all_movies = await self.get_all_movies()
            movies = [
                m
                for m in all_movies
                if m.get("title", "").lower() == title.lower()
                and (not year or m.get("year") == year)
            ]

        if movies:
            movie = movies[0]
            folder_path = movie.get("folderName") or movie.get("path")
            logger.debug(
                "radarr.folder_path_found", title=title, year=year, path=folder_path
            )
            return folder_path

        logger.warning("radarr.movie_not_found", title=title, year=year)
        return None

    async def get_quality_profiles(self) -> list[dict[str, Any]]:
        """
        Get all quality profiles

        Returns:
            list: Quality profiles
        """
        result = await self._request("GET", "/api/v3/qualityprofile")

        if isinstance(result, list):
            return result
        else:
            return []

    async def get_root_folders(self) -> list[dict[str, Any]]:
        """
        Get all root folders

        Returns:
            list: Root folders
        """
        result = await self._request("GET", "/api/v3/rootfolder")

        if isinstance(result, list):
            return result
        else:
            return []

    async def health_check(self) -> dict[str, Any]:
        """
        Check Radarr health

        Returns:
            dict: Health status information
        """
        if not self.settings.RADARR_URL or not self.settings.RADARR_API_KEY:
            return {
                "is_connected": False,
                "error": "Radarr not configured",
            }

        # Get system status
        status = await self._request("GET", "/api/v3/system/status")

        if status:
            movies = await self.get_all_movies()
            return {
                "is_connected": True,
                "version": status.get("version"),
                "movie_count": len(movies),
                "app_data": status.get("appData"),
            }
        else:
            return {
                "is_connected": False,
                "error": "Failed to connect to Radarr",
            }

"""
Radarr API Client

Handles communication with Radarr for movie library queries and folder path lookups.
Used to find where movies are stored for parallel version downloads.
"""

import logging
import aiohttp
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

log = logging.getLogger(__name__)


class RadarrClient:
    """Async client for Radarr API v3"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        """
        Initialize Radarr client

        Args:
            base_url: Radarr base URL (e.g., "http://10.0.0.63:7878")
            api_key: Radarr API key
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        """Ensure HTTP session exists with API key header"""
        if not self.session or self.session.closed:
            headers = {
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )

    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_body: Optional[Any] = None
    ) -> Any:
        """Make API request"""
        await self._ensure_session()

        if not self.session:
            raise RuntimeError("Failed to create session")

        url = urljoin(self.base_url, path)

        try:
            async with self.session.request(
                method, url, params=params, json=json_body
            ) as response:
                if response.status >= 400:
                    text = await response.text()
                    log.error(f"Radarr API error {response.status}: {text}")
                    raise RuntimeError(f"Radarr API error {response.status}: {text}")

                if response.content_type == "application/json":
                    return await response.json()
                return await response.text()
        except aiohttp.ClientError as e:
            log.error(f"Radarr request failed: {e}")
            raise

    async def get_movies(self) -> List[Dict[str, Any]]:
        """
        Get all movies in Radarr

        Returns:
            List of movie dicts
        """
        try:
            data = await self._request("GET", "/api/v3/movie")
            return data or []
        except Exception as e:
            log.error(f"Error getting Radarr movies: {e}")
            return []

    async def search_movie(
        self,
        title: str,
        year: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search for movie in Radarr library by title and year

        Args:
            title: Movie title
            year: Release year (optional, helps narrow results)

        Returns:
            Movie dict or None if not found
        """
        try:
            movies = await self.get_movies()

            # Normalize title for comparison
            search_title = title.lower().strip()

            # First try exact year match if year provided
            if year:
                for movie in movies:
                    movie_title = movie.get('title', '').lower().strip()
                    movie_year = movie.get('year')
                    if movie_title == search_title and movie_year == year:
                        return movie

            # Fallback to title-only match
            for movie in movies:
                movie_title = movie.get('title', '').lower().strip()
                if movie_title == search_title:
                    return movie

            log.info(f"Movie not found in Radarr: {title} ({year})")
            return None
        except Exception as e:
            log.error(f"Error searching for movie in Radarr: {e}")
            return None

    async def get_movie_by_id(self, radarr_id: int) -> Optional[Dict[str, Any]]:
        """
        Get movie by Radarr ID

        Args:
            radarr_id: Radarr's internal movie ID

        Returns:
            Movie dict or None
        """
        try:
            movie = await self._request("GET", f"/api/v3/movie/{radarr_id}")
            return movie
        except Exception as e:
            log.error(f"Error getting movie {radarr_id}: {e}")
            return None

    async def get_movie_folder(
        self,
        title: str,
        year: Optional[int] = None
    ) -> Optional[str]:
        """
        Get folder path for a movie

        Args:
            title: Movie title
            year: Release year

        Returns:
            Folder path string or None
        """
        movie = await self.search_movie(title, year)
        if movie and 'path' in movie:
            return movie['path']
        return None

    async def get_movie_file_info(
        self,
        title: str,
        year: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get file info for a movie (to show current quality)

        Args:
            title: Movie title
            year: Release year

        Returns:
            Dict with file info or None
        """
        movie = await self.search_movie(title, year)
        if not movie:
            return None

        file_info = {
            'folder': movie.get('path'),
            'has_file': movie.get('hasFile', False),
            'radarr_id': movie.get('id')
        }

        # Get movie file details if available
        if movie.get('movieFile'):
            movie_file = movie['movieFile']
            file_info.update({
                'file_path': movie_file.get('path'),
                'file_size': movie_file.get('size'),
                'quality': movie_file.get('quality', {}).get('quality', {}).get('name'),
                'resolution': movie_file.get('quality', {}).get('quality', {}).get('resolution')
            })

        return file_info

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to Radarr

        Returns:
            dict with success status and details
        """
        try:
            # Test by getting system status
            status = await self._request("GET", "/api/v3/system/status")

            # Get movie count
            movies = await self.get_movies()

            return {
                'success': True,
                'version': status.get('version', 'Unknown'),
                'movie_count': len(movies),
                'message': f"Connected to Radarr {status.get('version')}"
            }
        except Exception as e:
            log.error(f"Radarr connection test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def get_root_folders(self) -> List[Dict[str, Any]]:
        """
        Get root folders configured in Radarr

        Returns:
            List of root folder dicts
        """
        try:
            folders = await self._request("GET", "/api/v3/rootFolder")
            return folders or []
        except Exception as e:
            log.error(f"Error getting root folders: {e}")
            return []

    async def get_quality_profiles(self) -> List[Dict[str, Any]]:
        """
        Get quality profiles configured in Radarr

        Returns:
            List of quality profile dicts
        """
        try:
            profiles = await self._request("GET", "/api/v3/qualityProfile")
            return profiles or []
        except Exception as e:
            log.error(f"Error getting quality profiles: {e}")
            return []

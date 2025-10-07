import logging
import threading
from typing import Any, Dict, List, Optional

import aiohttp

log = logging.getLogger(__name__)


class RadarrClient:
    """Async helper for interacting with Radarr's API"""

    def __init__(self, base_url: str, api_key: str, *, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = threading.Lock()
        self._is_closing = False

    async def _ensure_session(self) -> None:
        if self._is_closing:
            raise RuntimeError("Radarr client is closing")

        if self._session and not self._session.closed:
            return

        with self._session_lock:
            if self._session and not self._session.closed:
                return

            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, ttl_dns_cache=300)
            headers = {
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            self._session = aiohttp.ClientSession(
                connector=connector,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )

    async def close(self) -> None:
        self._is_closing = True
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception as exc:  # pragma: no cover - best effort close
                log.debug("Error closing Radarr session: %s", exc)
            finally:
                self._session = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
    ) -> Any:
        await self._ensure_session()
        assert self._session is not None

        url = f"{self.base_url}{path}"

        async with self._session.request(method, url, params=params, json=json_body) as response:
            if response.status >= 400:
                text = await response.text()
                raise RuntimeError(f"Radarr API error {response.status}: {text}")
            if response.content_type == "application/json":
                return await response.json()
            return await response.text()

    async def get_movies(self) -> List[Dict[str, Any]]:
        data = await self._request("GET", "/api/v3/movie")
        return data or []

    async def get_root_folders(self) -> List[Dict[str, Any]]:
        data = await self._request("GET", "/api/v3/rootFolder")
        return data or []

    async def get_quality_profiles(self) -> List[Dict[str, Any]]:
        data = await self._request("GET", "/api/v3/qualityProfile")
        return data or []

    async def lookup_movie(
        self,
        *,
        tmdb_id: Optional[str] = None,
        imdb_id: Optional[str] = None,
        term: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, str] = {}
        if tmdb_id:
            params["term"] = f"tmdb:{tmdb_id}"
        elif imdb_id:
            params["term"] = f"imdb:{imdb_id}"
        elif term:
            params["term"] = term
        else:
            raise ValueError("A tmdb_id, imdb_id, or term is required for lookup")

        data = await self._request("GET", "/api/v3/movie/lookup", params=params)
        return data or []

    async def get_movie(
        self,
        *,
        tmdb_id: Optional[str] = None,
        imdb_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if tmdb_id:
            params["tmdbId"] = tmdb_id
        if imdb_id:
            params["imdbId"] = imdb_id
        if not params:
            raise ValueError("tmdb_id or imdb_id required to fetch Radarr movie")

        data = await self._request("GET", "/api/v3/movie", params=params)
        return data or []

    async def add_movie(self, movie_payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("POST", "/api/v3/movie", json_body=movie_payload)

    async def trigger_movie_search(self, movie_id: int) -> Dict[str, Any]:
        payload = {
            "name": "MoviesSearch",
            "movieIds": [int(movie_id)],
        }
        return await self._request("POST", "/api/v3/command", json_body=payload)

    async def search_releases(
        self,
        *,
        movie_id: Optional[int] = None,
        tmdb_id: Optional[str] = None,
        imdb_id: Optional[str] = None,
        term: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if movie_id:
            params["movieId"] = int(movie_id)
        if tmdb_id:
            params["tmdbId"] = tmdb_id
        if imdb_id:
            params["imdbId"] = imdb_id
        if term:
            params["term"] = term

        if not params:
            raise ValueError("A movie identifier or search term is required for release search")

        data = await self._request("GET", "/api/v3/release", params=params)
        return data or []

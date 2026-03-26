"""
qBittorrent Client
Async client for qBittorrent Web API
"""
from typing import Any
from urllib.parse import urljoin

import aiohttp

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class QBittorrentClient:
    """
    Async qBittorrent Web API client

    Handles authentication, torrent management, and category configuration.
    """

    def __init__(self):
        """Initialize qBittorrent client"""
        self.settings = get_settings()
        self._session: aiohttp.ClientSession | None = None
        self._cookie: str | None = None
        self._base_url = f"http://{self.settings.QBITTORRENT_HOST}:{self.settings.QBITTORRENT_PORT}"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.settings.QBITTORRENT_TIMEOUT)
            )
        return self._session

    async def close(self):
        """Close aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def login(self) -> bool:
        """
        Authenticate with qBittorrent

        Returns:
            bool: True if authentication successful
        """
        if not self.settings.QBITTORRENT_HOST:
            logger.warning("qbittorrent.not_configured")
            return False

        url = urljoin(self._base_url, "/api/v2/auth/login")
        data = {
            "username": self.settings.QBITTORRENT_USERNAME,
            "password": self.settings.QBITTORRENT_PASSWORD,
        }

        try:
            session = await self._get_session()
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    text = await response.text()
                    if text == "Ok.":
                        # Store cookie for subsequent requests
                        self._cookie = response.cookies.get("SID")
                        logger.info("qbittorrent.login_success")
                        return True
                    else:
                        logger.error("qbittorrent.login_failed", reason=text)
                        return False
                else:
                    logger.error("qbittorrent.login_failed", status=response.status)
                    return False

        except Exception as e:
            logger.error("qbittorrent.login_error", error=str(e))
            return False

    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> dict[str, Any] | list[Any] | str | None:
        """
        Make authenticated request to qBittorrent API

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            Response data or None if failed
        """
        # Ensure we're logged in
        if not self._cookie:
            if not await self.login():
                return None

        url = urljoin(self._base_url, endpoint)
        session = await self._get_session()

        # Add cookie to headers
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        kwargs["headers"]["Cookie"] = f"SID={self._cookie}"

        try:
            async with session.request(method, url, **kwargs) as response:
                if response.status == 403:
                    # Session expired, try to re-login
                    logger.info("qbittorrent.session_expired")
                    self._cookie = None
                    if await self.login():
                        # Retry request
                        kwargs["headers"]["Cookie"] = f"SID={self._cookie}"
                        async with session.request(method, url, **kwargs) as retry_response:
                            if retry_response.status == 200:
                                content_type = retry_response.headers.get("content-type", "")
                                if "application/json" in content_type:
                                    return await retry_response.json()
                                else:
                                    return await retry_response.text()
                    return None

                if response.status == 200:
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        return await response.json()
                    else:
                        return await response.text()
                else:
                    logger.warning(
                        "qbittorrent.request_failed",
                        endpoint=endpoint,
                        status=response.status,
                    )
                    return None

        except Exception as e:
            logger.error("qbittorrent.request_error", endpoint=endpoint, error=str(e))
            return None

    async def add_torrent(
        self,
        torrent_url: str,
        category: str | None = None,
        paused: bool = False,
        sequential: bool = False,
    ) -> bool:
        """
        Add torrent from URL

        Args:
            torrent_url: URL to .torrent file
            category: Category to assign
            paused: Add in paused state
            sequential: Enable sequential download

        Returns:
            bool: True if added successfully
        """
        if category is None:
            category = self.settings.QBITTORRENT_CATEGORY

        data = {
            "urls": torrent_url,
            "category": category,
            "paused": "true" if paused else "false",
            "sequentialDownload": "true" if sequential else "false",
        }

        result = await self._request("POST", "/api/v2/torrents/add", data=data)

        if result == "Ok.":
            logger.info(
                "qbittorrent.torrent_added",
                url=torrent_url,
                category=category,
            )
            return True
        else:
            logger.error("qbittorrent.torrent_add_failed", url=torrent_url)
            return False

    async def get_torrents(
        self, category: str | None = None, filter: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get list of torrents

        Args:
            category: Filter by category
            filter: Filter by status (downloading, completed, paused, active, etc.)

        Returns:
            list: Torrent info dictionaries
        """
        params = {}
        if category:
            params["category"] = category
        if filter:
            params["filter"] = filter

        result = await self._request("GET", "/api/v2/torrents/info", params=params)

        if isinstance(result, list):
            return result
        else:
            logger.warning("qbittorrent.get_torrents_failed")
            return []

    async def get_torrent_info(self, torrent_hash: str) -> dict[str, Any] | None:
        """
        Get detailed info for a specific torrent

        Args:
            torrent_hash: Torrent hash

        Returns:
            dict: Torrent info or None
        """
        torrents = await self.get_torrents()

        for torrent in torrents:
            if torrent.get("hash") == torrent_hash:
                return torrent

        return None

    async def delete_torrent(
        self, torrent_hash: str, delete_files: bool = False
    ) -> bool:
        """
        Delete a torrent

        Args:
            torrent_hash: Torrent hash
            delete_files: Also delete downloaded files

        Returns:
            bool: True if deleted successfully
        """
        data = {
            "hashes": torrent_hash,
            "deleteFiles": "true" if delete_files else "false",
        }

        result = await self._request("POST", "/api/v2/torrents/delete", data=data)

        if result == "Ok.":
            logger.info("qbittorrent.torrent_deleted", hash=torrent_hash)
            return True
        else:
            return False

    async def create_category(self, category: str) -> bool:
        """
        Create a category

        Args:
            category: Category name

        Returns:
            bool: True if created successfully
        """
        data = {"category": category, "savePath": ""}

        result = await self._request("POST", "/api/v2/torrents/createCategory", data=data)

        if result == "Ok." or result is None:  # qBit returns nothing on success sometimes
            logger.info("qbittorrent.category_created", category=category)
            return True
        else:
            return False

    async def get_categories(self) -> dict[str, Any]:
        """
        Get all categories

        Returns:
            dict: Categories dictionary
        """
        result = await self._request("GET", "/api/v2/torrents/categories")

        if isinstance(result, dict):
            return result
        else:
            return {}

    async def health_check(self) -> dict[str, Any]:
        """
        Check qBittorrent health

        Returns:
            dict: Health status information
        """
        is_connected = await self.login()

        if not is_connected:
            return {
                "is_connected": False,
                "error": "Failed to authenticate",
            }

        # Get version info
        version = await self._request("GET", "/api/v2/app/version")
        torrents = await self.get_torrents()

        return {
            "is_connected": True,
            "version": version,
            "torrent_count": len(torrents),
            "categories": await self.get_categories(),
        }

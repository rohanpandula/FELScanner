"""
qBittorrent Web API Client

Handles communication with qBittorrent for adding and managing torrents.
Supports both authenticated and LAN-only (no auth) modes.
"""

import logging
import aiohttp
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

log = logging.getLogger(__name__)


class QBittorrentClient:
    """Async client for qBittorrent Web API"""

    def __init__(self, host: str, port: int = 8080, username: str = "", password: str = ""):
        """
        Initialize qBittorrent client

        Args:
            host: qBittorrent host (e.g., "10.0.0.63")
            port: WebUI port (default 8080)
            username: Username for authentication (empty for LAN mode)
            password: Password for authentication (empty for LAN mode)
        """
        self.base_url = f"http://{host}:{port}"
        self.username = username
        self.password = password
        self.session: Optional[aiohttp.ClientSession] = None
        self._session_cookie: Optional[str] = None
        self._requires_auth = bool(username and password)

    async def _ensure_session(self):
        """Ensure HTTP session exists and is authenticated if needed"""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

        # Authenticate if required and not yet authenticated
        if self._requires_auth and not self._session_cookie:
            await self._login()

    async def _login(self):
        """Authenticate with qBittorrent WebUI"""
        if not self.session:
            return

        try:
            login_url = urljoin(self.base_url, "/api/v2/auth/login")
            data = aiohttp.FormData()
            data.add_field('username', self.username)
            data.add_field('password', self.password)

            async with self.session.post(login_url, data=data) as response:
                if response.status == 200:
                    text = await response.text()
                    if text == "Ok.":
                        # Extract SID cookie
                        cookies = self.session.cookie_jar.filter_cookies(self.base_url)
                        if 'SID' in cookies:
                            self._session_cookie = cookies['SID'].value
                            log.info("qBittorrent authentication successful")
                        return

                log.error(f"qBittorrent login failed: {response.status}")
                raise RuntimeError(f"qBittorrent authentication failed: {response.status}")
        except Exception as e:
            log.error(f"Error during qBittorrent login: {e}")
            raise

    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def add_torrent(
        self,
        url_or_magnet: str,
        save_path: str,
        category: str = "movies",
        paused: bool = False,
        sequential: bool = False
    ) -> Dict[str, Any]:
        """
        Add torrent to qBittorrent

        Args:
            url_or_magnet: Torrent URL or magnet link
            save_path: Directory to save files
            category: Category for organization
            paused: Add in paused state
            sequential: Enable sequential download

        Returns:
            dict with status and torrent hash
        """
        await self._ensure_session()

        if not self.session:
            raise RuntimeError("Failed to create session")

        try:
            add_url = urljoin(self.base_url, "/api/v2/torrents/add")

            data = aiohttp.FormData()
            data.add_field('urls', url_or_magnet)
            data.add_field('savepath', save_path)
            data.add_field('category', category)
            data.add_field('paused', 'true' if paused else 'false')
            data.add_field('sequentialDownload', 'true' if sequential else 'false')

            async with self.session.post(add_url, data=data) as response:
                if response.status == 200:
                    text = await response.text()
                    if text == "Ok.":
                        log.info(f"Successfully added torrent to qBittorrent: {save_path}")

                        # Try to get hash by looking for recently added torrent
                        # (qBittorrent doesn't return hash directly from add endpoint)
                        torrents = await self.get_torrents(category=category)
                        if torrents:
                            # Return most recently added torrent in this category
                            latest = max(torrents, key=lambda t: t.get('added_on', 0))
                            return {
                                'success': True,
                                'hash': latest.get('hash'),
                                'name': latest.get('name')
                            }

                        return {'success': True, 'hash': None}
                    else:
                        log.error(f"qBittorrent add failed: {text}")
                        return {'success': False, 'error': text}
                else:
                    error_text = await response.text()
                    log.error(f"qBittorrent add failed: {response.status} - {error_text}")
                    return {'success': False, 'error': f"HTTP {response.status}"}
        except Exception as e:
            log.error(f"Error adding torrent to qBittorrent: {e}")
            return {'success': False, 'error': str(e)}

    async def get_torrents(
        self,
        category: Optional[str] = None,
        filter_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of torrents

        Args:
            category: Filter by category
            filter_status: Filter by status (downloading, completed, etc.)

        Returns:
            List of torrent info dicts
        """
        await self._ensure_session()

        if not self.session:
            return []

        try:
            info_url = urljoin(self.base_url, "/api/v2/torrents/info")
            params = {}
            if category:
                params['category'] = category
            if filter_status:
                params['filter'] = filter_status

            async with self.session.get(info_url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    log.error(f"Failed to get torrents: {response.status}")
                    return []
        except Exception as e:
            log.error(f"Error getting torrents: {e}")
            return []

    async def get_torrent_info(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed info for specific torrent

        Args:
            torrent_hash: Torrent hash

        Returns:
            Torrent info dict or None
        """
        torrents = await self.get_torrents()
        for torrent in torrents:
            if torrent.get('hash') == torrent_hash:
                return torrent
        return None

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to qBittorrent

        Returns:
            dict with success status and details
        """
        try:
            await self._ensure_session()

            if not self.session:
                return {'success': False, 'error': 'Failed to create session'}

            # Test API by getting version
            version_url = urljoin(self.base_url, "/api/v2/app/version")
            async with self.session.get(version_url) as response:
                if response.status == 200:
                    version = await response.text()

                    # Get torrent count
                    torrents = await self.get_torrents()

                    return {
                        'success': True,
                        'version': version,
                        'torrent_count': len(torrents),
                        'message': f'Connected to qBittorrent {version}'
                    }
                else:
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}'
                    }
        except Exception as e:
            log.error(f"qBittorrent connection test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def get_categories(self) -> Dict[str, Dict]:
        """
        Get all categories

        Returns:
            Dict mapping category names to category info
        """
        await self._ensure_session()

        if not self.session:
            return {}

        try:
            categories_url = urljoin(self.base_url, "/api/v2/torrents/categories")
            async with self.session.get(categories_url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    log.error(f"Failed to get categories: {response.status}")
                    return {}
        except Exception as e:
            log.error(f"Error getting categories: {e}")
            return {}

"""
Download Manager

Orchestrates the complete workflow:
1. IPT discovery → Parse quality
2. Check Plex library → Get current quality
3. Smart upgrade detection → Should we notify?
4. Get Radarr folder path
5. Send Telegram approval request
6. Execute download on approval
"""

import logging
import hashlib
import time
import json
import re
from typing import Dict, Optional, Any
from datetime import datetime

log = logging.getLogger(__name__)


class DownloadManager:
    """Orchestrates IPT discoveries through to qBittorrent downloads"""

    def __init__(self, qbt_client, radarr_client, telegram_handler, upgrade_detector, scanner_db):
        """
        Initialize download manager

        Args:
            qbt_client: QBittorrentClient instance
            radarr_client: RadarrClient instance
            telegram_handler: TelegramDownloadHandler instance
            upgrade_detector: UpgradeDetector instance
            scanner_db: MovieDatabase instance from scanner
        """
        self.qbt = qbt_client
        self.radarr = radarr_client
        self.telegram = telegram_handler
        self.upgrade_detector = upgrade_detector
        self.db = scanner_db

        # Set callback handler for Telegram responses
        self.telegram.set_callback_handler(self.execute_download)

    async def process_ipt_discovery(self, torrent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point when IPT finds new torrent

        Args:
            torrent_data: Dict with torrent info (title, url/magnet_link, etc.)

        Returns:
            Dict with processing status and details
        """
        try:
            # Parse torrent title
            parsed = self.parse_torrent_title(torrent_data['title'])
            if not parsed:
                return {"status": "skip", "reason": "Could not parse torrent title"}

            log.info(f"Processing IPT discovery: {parsed['title']} ({parsed['year']})")

            # Look up movie in Plex database
            movie = self.find_movie_in_db(parsed['title'], parsed.get('year'))

            if not movie:
                return {
                    "status": "skip",
                    "reason": "Movie not in your Plex library"
                }

            # Get current quality details
            current_quality = self.get_current_quality(movie)

            # Parse new quality from torrent
            new_quality = self.upgrade_detector.parse_torrent_quality(torrent_data['title'])

            # Smart upgrade detection
            should_notify, reason = self.upgrade_detector.is_notification_worthy(
                current_quality,
                new_quality
            )

            if not should_notify:
                log.info(f"Skipping {movie['title']}: {reason}")
                return {"status": "skip", "reason": reason}

            log.info(f"Upgrade detected for {movie['title']}: {reason}")

            # Get Radarr folder path
            radarr_folder = await self.radarr.get_movie_folder(
                parsed['title'],
                parsed.get('year')
            )

            if not radarr_folder:
                return {
                    "status": "error",
                    "reason": "Movie not found in Radarr or no folder path"
                }

            # Build download request
            request_id = self.generate_request_id(movie['title'], new_quality)

            download_request = {
                'request_id': request_id,
                'movie_title': movie['title'],
                'year': movie.get('year'),
                'current_quality': self.format_current_quality(current_quality),
                'new_quality': self.format_new_quality(new_quality),
                'upgrade_reason': reason,
                'torrent_url': torrent_data.get('magnet_link') or torrent_data.get('url'),
                'torrent_title': torrent_data['title'],
                'target_folder': radarr_folder,
                'quality_type': 'fel' if new_quality.get('is_fel') else 'dv' if new_quality.get('dv_profile') else 'hdr',
                'created_at': datetime.now().isoformat()
            }

            # Store in database (we'll add this method)
            self.store_pending_download(request_id, download_request)

            # Send Telegram approval request
            message_id = self.telegram.send_approval_request(download_request)

            if message_id:
                log.info(f"Sent approval request for {movie['title']} (request_id: {request_id})")
                return {
                    "status": "pending_approval",
                    "request_id": request_id,
                    "message_id": message_id
                }
            else:
                return {
                    "status": "error",
                    "reason": "Failed to send Telegram notification"
                }

        except Exception as e:
            log.error(f"Error processing IPT discovery: {e}", exc_info=True)
            return {
                "status": "error",
                "reason": str(e)
            }

    async def execute_download(self, request_id: str, action: str = "approved") -> Dict[str, Any]:
        """
        Execute approved download

        Args:
            request_id: Download request ID
            action: Action taken (approved/declined)

        Returns:
            Dict with execution result
        """
        if action != "approved":
            log.info(f"Download {request_id} was declined")
            return {"success": True, "action": "declined"}

        try:
            # Get request details from database
            download_data = self.get_pending_download(request_id)

            if not download_data:
                return {"success": False, "error": "Download request not found"}

            movie_title = download_data['movie_title']
            target_folder = download_data['target_folder']
            torrent_url = download_data['torrent_url']
            quality_type = download_data.get('quality_type', 'unknown')

            log.info(f"Executing download: {movie_title} to {target_folder}")

            # Send to qBittorrent
            result = await self.qbt.add_torrent(
                url_or_magnet=torrent_url,
                save_path=target_folder,
                category=f"movies-{quality_type}",
                paused=False,  # Will use settings
                sequential=True  # Will use settings
            )

            if result.get('success'):
                # Update database status
                self.mark_download_started(request_id, result.get('hash'))

                # Send confirmation notification
                self.telegram.send_download_started(
                    movie_title,
                    download_data['new_quality'],
                    target_folder
                )

                log.info(f"Successfully started download: {movie_title}")
                return {
                    "success": True,
                    "movie_title": movie_title,
                    "torrent_hash": result.get('hash')
                }
            else:
                error = result.get('error', 'Unknown error')
                log.error(f"Failed to add torrent: {error}")

                # Send error notification
                self.telegram.send_download_error(movie_title, error)

                return {
                    "success": False,
                    "error": error
                }

        except Exception as e:
            log.error(f"Error executing download: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def parse_torrent_title(self, title: str) -> Optional[Dict[str, Any]]:
        """
        Parse movie title and year from torrent title

        Args:
            title: Torrent title string

        Returns:
            Dict with parsed info or None
        """
        # Common pattern: "Movie Name 2021 2160p DV FEL..."
        # Try to extract title and year

        # Pattern 1: Title (Year) or Title.Year
        pattern1 = r'^(.+?)[.\s]+(\d{4})[.\s]'
        match = re.search(pattern1, title)

        if match:
            movie_title = match.group(1).replace('.', ' ').strip()
            year = int(match.group(2))

            # Clean up title
            movie_title = re.sub(r'\s+', ' ', movie_title)

            return {
                'title': movie_title,
                'year': year
            }

        # Pattern 2: Just grab everything before first year-like number
        pattern2 = r'^(.+?)\s+(\d{4})'
        match = re.search(pattern2, title)

        if match:
            movie_title = match.group(1).strip()
            year = int(match.group(2))

            return {
                'title': movie_title,
                'year': year
            }

        log.warning(f"Could not parse torrent title: {title}")
        return None

    def find_movie_in_db(self, title: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Find movie in Plex database

        Args:
            title: Movie title
            year: Release year (optional)

        Returns:
            Movie dict or None
        """
        try:
            # Use scanner database to query
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Normalize title for comparison
                search_title = title.lower().strip()

                if year:
                    # Try with year from extra_data
                    cursor.execute("""
                        SELECT * FROM movies
                        WHERE LOWER(title) = ?
                        AND json_extract(extra_data, '$.year') = ?
                    """, (search_title, str(year)))

                    result = cursor.fetchone()
                    if result:
                        return dict(result)

                # Fallback to title-only search
                cursor.execute("""
                    SELECT * FROM movies
                    WHERE LOWER(title) = ?
                    LIMIT 1
                """, (search_title,))

                result = cursor.fetchone()
                if result:
                    return dict(result)

                return None

        except Exception as e:
            log.error(f"Error finding movie in database: {e}")
            return None

    def get_current_quality(self, movie: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract current quality details from movie record

        Args:
            movie: Movie dict from database

        Returns:
            Quality dict
        """
        extra_data = {}
        if movie.get('extra_data'):
            try:
                extra_data = json.loads(movie['extra_data'])
            except:
                pass

        return {
            'dv_profile': movie.get('dv_profile'),
            'dv_fel': bool(movie.get('dv_fel')),
            'has_atmos': bool(movie.get('has_atmos')),
            'file_size': extra_data.get('file_size'),
            'bitrate': extra_data.get('video_bitrate'),
            'resolution': self.guess_resolution(extra_data)
        }

    def guess_resolution(self, extra_data: Dict) -> str:
        """Guess resolution from available data"""
        # Could be enhanced based on extra_data
        return extra_data.get('resolution', 'unknown')

    def format_current_quality(self, quality: Dict[str, Any]) -> str:
        """Format current quality for display"""
        lines = []

        # DV info
        if quality.get('dv_profile'):
            fel_status = " FEL" if quality.get('dv_fel') else " MEL"
            lines.append(f"• DV Profile {quality['dv_profile']}{fel_status}")
        else:
            lines.append("• HDR10 / SDR")

        # File size
        if quality.get('file_size'):
            size_gb = quality['file_size'] / (1024 ** 3)
            lines.append(f"• {size_gb:.1f} GB")

        # Bitrate
        if quality.get('bitrate'):
            lines.append(f"• {quality['bitrate']}")

        # Resolution
        if quality.get('resolution') and quality['resolution'] != 'unknown':
            lines.append(f"• {quality['resolution']}")

        # Atmos
        if quality.get('has_atmos'):
            lines.append("• TrueHD Atmos ✓")

        return "\n".join(lines) if lines else "Unknown"

    def format_new_quality(self, quality: Dict[str, Any]) -> str:
        """Format new quality for display"""
        lines = []

        # DV info
        if quality.get('dv_profile'):
            if quality.get('is_fel'):
                lines.append(f"• DV Profile {quality['dv_profile']} FEL (BL+EL+RPU)")
            else:
                lines.append(f"• DV Profile {quality['dv_profile']}")
        else:
            lines.append("• HDR10")

        # Resolution
        if quality.get('resolution') and quality['resolution'] != 'unknown':
            lines.append(f"• {quality['resolution']}")

        # Atmos
        if quality.get('has_atmos'):
            lines.append("• TrueHD Atmos ✓")

        lines.append("• From IPTorrents")

        return "\n".join(lines)

    def generate_request_id(self, movie_title: str, quality: Dict) -> str:
        """Generate unique request ID"""
        unique_str = f"{movie_title}{quality}{time.time()}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]

    # Database methods (delegate to scanner database)
    def store_pending_download(self, request_id: str, download_data: Dict):
        """Store pending download in database"""
        self.db.store_pending_download(request_id, download_data)

    def get_pending_download(self, request_id: str) -> Optional[Dict]:
        """Get pending download from database"""
        return self.db.get_pending_download(request_id)

    def mark_download_started(self, request_id: str, torrent_hash: Optional[str]):
        """Mark download as started in database"""
        self.db.mark_download_started(request_id, torrent_hash)

"""
FELScanner Integration Modules

Provides API clients and orchestration for external services:
- qBittorrent: Direct torrent download management
- Radarr: Movie library and folder path queries
- Telegram: Interactive approval notifications
- UpgradeDetector: Smart notification filtering
- DownloadManager: Orchestrates the complete workflow
"""

from .qbittorrent import QBittorrentClient
from .radarr import RadarrClient
from .upgrade_detector import UpgradeDetector
from .telegram_handler import TelegramDownloadHandler
from .download_manager import DownloadManager

__all__ = [
    'QBittorrentClient',
    'RadarrClient',
    'UpgradeDetector',
    'TelegramDownloadHandler',
    'DownloadManager'
]

# IPT/qBittorrent Integration

## Overview

This integration enables automated discovery, approval, and downloading of quality upgrades from IPTorrents directly into qBittorrent. It uses intelligent upgrade detection to notify you only when a torrent represents a meaningful quality improvement for movies in your Plex library.

## Architecture

```
IPTorrents RSS → Parser → Upgrade Detector → Telegram Approval → qBittorrent Download
                               ↓
                         Radarr (folder lookup)
                               ↓
                         Plex Database (current quality)
```

## Components

### 1. **Upgrade Detector** (`integrations/upgrade_detector.py`)
Smart quality comparison engine that determines if a new torrent is worth downloading.

**Features:**
- DV Profile detection (Profile 5, 7, 8)
- FEL (Full Enhancement Layer) detection
- Atmos audio detection
- Resolution comparison (720p, 1080p, 2160p)
- Configurable notification rules

**Example Rules:**
- ✅ Notify: HDR10 → P7 FEL
- ✅ Notify: P5 → P7 FEL
- ❌ Skip: P7 FEL → P7 FEL (duplicate)
- ✅ Notify: P5 + Atmos when current has no Atmos

### 2. **qBittorrent Client** (`integrations/qbittorrent.py`)
Async client for qBittorrent Web API.

**Features:**
- Add torrents via URL or magnet link
- Configure save path per torrent
- Set category for organization
- Enable sequential download
- Monitor torrent status

**Connection:**
- Supports both authenticated and LAN-only modes
- Auto-reconnects across event loops
- Session cookie management

### 3. **Radarr Client** (`integrations/radarr.py`)
Async client for Radarr API v3.

**Features:**
- Movie lookup by title and year
- Get movie folder paths
- Query file quality information
- Root folder and quality profile queries

**Use Case:**
When a quality upgrade is detected, Radarr provides the exact folder path where the new version should be downloaded (parallel to existing file).

### 4. **Telegram Handler** (`integrations/telegram_handler.py`)
Sends approval requests and status updates via Telegram.

**Features:**
- Rich approval messages with inline buttons
- Current vs. New quality comparison
- Download progress notifications
- Error notifications
- Callback handling for button presses

### 5. **Download Manager** (`integrations/download_manager.py`)
Orchestrates the complete workflow.

**Workflow:**
1. **IPT Discovery** → Parse torrent title
2. **Library Check** → Find movie in Plex database
3. **Upgrade Detection** → Compare current vs. new quality
4. **Radarr Lookup** → Get destination folder
5. **Telegram Approval** → Send interactive notification
6. **Execute Download** → Add to qBittorrent on approval

## Configuration

All settings are stored in `settings.json`:

```json
{
  "qbittorrent_host": "10.0.0.63",
  "qbittorrent_port": 8080,
  "qbittorrent_username": "",
  "qbittorrent_password": "",
  "qbittorrent_category": "movies-fel",
  "qbit_pause_on_add": false,
  "qbit_sequential_download": true,

  "radarr_url": "http://10.0.0.35:7878",
  "radarr_api_key": "your-api-key",
  "radarr_root_path": "/mnt/user/Media/Movies/",

  "notify_fel": true,
  "notify_fel_from_p5": true,
  "notify_fel_from_hdr": true,
  "notify_fel_duplicates": false,
  "notify_dv": false,
  "notify_dv_from_hdr": true,
  "notify_dv_profile_upgrades": true,
  "notify_atmos": false,
  "notify_atmos_only_if_no_atmos": true,
  "notify_atmos_with_dv_upgrade": true,
  "notify_resolution": false,
  "notify_resolution_only_upgrades": true,
  "notify_only_library_movies": true,
  "notify_expire_hours": 24,

  "notify_download_start": true,
  "notify_download_complete": true,
  "notify_download_error": true
}
```

## Usage

### Via Web UI

1. **Configure Integration**
   - Settings → IPTorrents → Enable integration
   - Settings → qBittorrent → Configure host/port
   - Settings → Radarr → Configure URL and API key

2. **Monitor IPT Feed**
   - IPT tab shows recent torrents
   - Green badge indicates quality upgrades detected

3. **Approve Downloads**
   - Receive Telegram notification with quality comparison
   - Tap "✅ Download" to approve or "❌ Skip" to decline
   - Downloads start automatically on approval

4. **Track Progress**
   - "Pending Approvals" shows awaiting downloads
   - "Download History" shows completed downloads
   - qBittorrent handles actual download

### Programmatically

```python
from integrations import (
    QBittorrentClient,
    RadarrClient,
    TelegramDownloadHandler,
    UpgradeDetector,
    DownloadManager
)

# Initialize clients
qbt = QBittorrentClient(host="10.0.0.63", port=8080)
radarr = RadarrClient(
    base_url="http://10.0.0.35:7878",
    api_key="your-api-key"
)
telegram = TelegramDownloadHandler(
    token="bot-token",
    chat_id="your-chat-id"
)
detector = UpgradeDetector(notification_config)

# Initialize download manager
manager = DownloadManager(
    qbt_client=qbt,
    radarr_client=radarr,
    telegram_handler=telegram,
    upgrade_detector=detector,
    scanner_db=db
)

# Process IPT discovery
torrent_data = {
    'title': 'Dune 2021 2160p UHD BluRay DV FEL BL+EL+RPU Atmos TrueHD 7.1 x265',
    'magnet_link': 'magnet:?xt=urn:btih:...'
}

result = await manager.process_ipt_discovery(torrent_data)
# Result: {"status": "pending_approval", "request_id": "abc123", "message_id": 456}
```

## Testing

Comprehensive test suite in `test_integration.py`:

```bash
python3 test_integration.py
```

**Test Coverage:**
- ✅ Upgrade detector logic (5 scenarios)
- ✅ Radarr movie lookup
- ✅ Database operations (pending downloads, history)
- ✅ Torrent title parsing

## API Endpoints

### Get Pending Approvals
```
GET /api/downloads/pending
```

### Get Download History
```
GET /api/downloads/history?limit=50
```

### Approve Download
```
POST /api/downloads/approve
{
  "request_id": "abc123"
}
```

## Database Schema

### pending_downloads
```sql
CREATE TABLE pending_downloads (
    request_id TEXT PRIMARY KEY,
    movie_title TEXT,
    year INTEGER,
    torrent_url TEXT,
    target_folder TEXT,
    quality_type TEXT,
    status TEXT,
    telegram_message_id INTEGER,
    created_at TEXT,
    expires_at TEXT,
    download_data TEXT
);
```

### download_history
```sql
CREATE TABLE download_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT,
    movie_title TEXT,
    quality_type TEXT,
    torrent_hash TEXT,
    target_folder TEXT,
    status TEXT,
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT
);
```

## Example Workflow

1. **IPTorrents RSS refreshes** (every 5-10 minutes)
   - New torrent: "The Batman 2022 2160p DV Profile 7 FEL Atmos x265"

2. **Parser extracts metadata:**
   - Title: "The Batman"
   - Year: 2022
   - Quality: DV Profile 7, FEL, 2160p, Atmos

3. **Database lookup:**
   - Movie found in Plex library
   - Current quality: DV Profile 5, MEL, 2160p, No Atmos

4. **Upgrade detection:**
   - ✅ P5 → P7 FEL is a significant upgrade
   - ✅ Also gains Atmos audio
   - Decision: **NOTIFY**

5. **Radarr lookup:**
   - Movie folder: `/movies/The Batman (2022)/`

6. **Telegram notification sent:**
   ```
   🎬 Quality Upgrade Available

   The Batman (2022)

   Current Quality:
   • DV Profile 5 MEL
   • 2160p
   • 45.2 GB

   New Quality:
   • DV Profile 7 FEL (BL+EL+RPU)
   • 2160p
   • TrueHD Atmos ✓
   • From IPTorrents

   Reason: Upgrade: DV P5 → P7 FEL ⭐

   [✅ Download]  [❌ Skip]
   ```

7. **User approves → Download starts:**
   - Added to qBittorrent
   - Category: "movies-fel"
   - Save path: `/movies/The Batman (2022)/`
   - Sequential download enabled

8. **Status tracked:**
   - Database updated: status → "downloading"
   - Telegram: "✅ Download started for The Batman"
   - qBittorrent monitors progress

## Benefits

1. **Intelligent Filtering**
   - Only notifies for meaningful upgrades
   - Prevents duplicate downloads
   - Respects your quality preferences

2. **User Control**
   - Manual approval required
   - Full quality comparison before deciding
   - 24-hour expiration prevents stale requests

3. **Seamless Integration**
   - Works with existing Plex library
   - Integrates with Radarr folder structure
   - Uses qBittorrent's powerful download engine

4. **Telegram Convenience**
   - Approve downloads from anywhere
   - Rich notifications with inline buttons
   - Progress tracking and error alerts

## Future Enhancements

- [ ] Automatic download for specific quality tiers
- [ ] Size-based filtering (skip if >100GB)
- [ ] Seeder count threshold
- [ ] Automatic cleanup of old versions
- [ ] Integration with other trackers (BTN, PTP)
- [ ] Web UI for approval (alternative to Telegram)

## Troubleshooting

### qBittorrent connection fails
- Verify host/port are correct
- Check if WebUI is enabled in qBittorrent settings
- For authenticated mode, ensure username/password match

### Radarr movies not found
- Ensure movie exists in Radarr library
- Check title/year matching (case-insensitive)
- Verify API key is correct

### Telegram notifications not received
- Check bot token is valid
- Verify chat_id is correct
- Ensure bot is started (send /start to bot)

### Downloads not starting
- Check qBittorrent category exists
- Verify save path is writable
- Check torrent URL/magnet is valid

## Credits

Built with:
- [qBittorrent Web API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-Documentation)
- [Radarr API v3](https://radarr.video/docs/api/)
- [python-telegram-bot](https://python-telegram-bot.org/)
- aiohttp for async HTTP requests

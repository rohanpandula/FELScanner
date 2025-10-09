# FELScanner

FELScanner is a Dolby Vision/TrueHD intelligence layer for Plex. It crawls your library, curates collections, produces detailed reports, and ships with a Vue/Tailwind control center that surfaces live Dolby Vision metrics, Atmos coverage, IPTorrents discoveries, and smart connection monitoring at a glance. **Now with integrated Radarr + qBittorrent download approval workflow for automated FEL upgrades!**

## Key Capabilities

- **Plex Dolby Vision Profiler** – classifies every movie by Dolby Vision profile (highlighting Profile 7 FEL), FEL/MEL status, and Atmos availability.
- **Smart Collections** – keeps Plex collections (All DV, FEL, Atmos) in sync based on scan results with one-click verify & repair.
- **Automated Download Approval System** ⭐ **NEW** – intelligent torrent discovery with Telegram approval workflow:
  - Monitors IPTorrents for Profile 7 FEL releases
  - Smart upgrade detection (P5→P7 FEL, HDR10→DV, resolution upgrades, Atmos additions)
  - Sends Telegram notifications with inline Approve/Decline buttons ONLY for actual upgrades
  - Downloads to same folder as existing movie for Plex version stacking
  - Tracks pending approvals and active downloads in dashboard
  - Granular notification rules (17 customizable settings)
- **On-demand Metadata Explorer** – cached Plex metadata with click-to-run ffprobe analysis, version switching, and per-track details.
- **Insight Dashboard (Vue + Tailwind)** – the landing page (`/`) shows live scan status, DV/Atmos ratios, FEL overlaps, yearly growth trends, recent additions, connection health, pending approvals, active downloads, and cached IPTorrents hits.
- **Intelligent Connection Monitoring** – automatic periodic health checks for all external services with smart status messages, test buttons, and one-click connection attempts.
- **Comprehensive Settings Panel** – configure all services (Plex, Telegram, Radarr, qBittorrent, IPTorrents, FlareSolverr) through an integrated tabbed interface with live connection testing.
- **Detailed Exports** – generates JSON/CSV snapshots (`exports/`) with per-title metadata including bitrate, file size, and audio tracks.
- **FlareSolverr-powered IPTorrents Monitor** – polls IPTorrents via FlareSolverr, tracks new FEL releases, and exposes cached results to the dashboard.
- **REST endpoints for automation** – JSON APIs expose scan state, rich DV metrics, report manifests, connection telemetry, and download management for external tooling.

## Architecture Overview

```
FELScanner (Flask)
├── app.py                 # Flask routes, background jobs, REST endpoints
├── scanner.py             # Plex scanning engine, SQLite persistence
├── integrations/          # ⭐ NEW: Download approval system
│   ├── __init__.py        # Module exports
│   ├── qbittorrent.py     # qBittorrent Web API client (async)
│   ├── radarr.py          # Radarr API v3 client (async)
│   ├── upgrade_detector.py # Smart upgrade logic (P5→P7, HDR→DV, etc.)
│   ├── telegram_handler.py # Telegram approval notifications with inline buttons
│   └── download_manager.py # Orchestrates discovery → approval → download
├── templates/
│   ├── index.html         # Vue/Tailwind single-page control center
│   ├── settings.html      # Dedicated settings page (4 tabs: Connections, Notifications, Downloads, Advanced)
│   ├── dashboard.html     # Legacy dashboard view
│   └── iptscanner.html    # Legacy IPTorrents settings
├── static/js/
│   ├── newgui-app.js      # Vue app powering the new control center
│   ├── settings.js        # Settings page JavaScript (tab switching, API calls, test buttons)
│   └── main.js            # Legacy dashboard interactions
├── iptscanner/
│   ├── fetch-once.js      # FlareSolverr one-shot fetch
│   ├── monitor-iptorrents.js # Background monitor (Node.js)
│   └── package.json       # Node dependencies (axios, cheerio, cron, sqlite3)
└── exports/, data/        # Generated reports, SQLite movie DB, download history
```

### Backend data flow

1. `scanner.PlexDVScanner` walks your Plex movie library via PlexAPI, captures profile/Atmos metadata, and stores results in `exports/movie_database.db`.
2. REST helpers in `app.py` compute roll-up metrics (profile distribution, FEL/Atmos overlaps, growth by year, quality averages) and expose them under `/api/metrics`.
3. `/api/status` reports scan/monitor state and last collection changes; `/api/connections` summarizes Plex/IPT/Telegram/Radarr/qBittorrent health.
4. IPTorrents fetches flow through `run_ipt_scanner()` → `iptradar/fetch-once.js` → FlareSolverr → cached JSON → download approval workflow.

### Download approval workflow ⭐ NEW

```
IPT Scanner discovers new torrent
          ↓
download_manager.process_ipt_discovery()
          ↓
upgrade_detector.analyze_upgrade() ← Compares against Plex library
          ↓
telegram_handler.send_approval_request() ← Only if actual upgrade detected
          ↓
User clicks Approve/Decline in Telegram
          ↓
/telegram/webhook receives callback
          ↓
download_manager.approve() OR download_manager.decline()
          ↓
qBittorrent adds torrent to same folder as existing movie
          ↓
Plex refreshes and detects new version for stacking
```

**Key Features:**
- **Smart filtering**: Only notifies for genuine upgrades (not duplicates or downgrades)
- **17 notification rules**: Customize exactly when to be notified (P5→P7 FEL only, DV from HDR, Atmos with DV upgrade, etc.)
- **Version stacking**: Downloads to same path as existing file so Plex auto-stacks versions
- **Expiration**: Pending approvals auto-expire after configurable hours (default: 24h)
- **Download tracking**: Dashboard shows pending approvals and active qBittorrent progress

### REST endpoints

| Endpoint            | Description                                          |
|---------------------|------------------------------------------------------|
| `GET /api/status`   | Scan/monitor state plus last DV/Atmos counts         |
| `GET /api/metrics`  | Dolby Vision analytics (profiles, overlaps, quality) |
| `GET /api/reports`  | Recent report manifest (filename, timestamp, size)   |
| `GET /api/connections` | Plex/IPT/Telegram/Radarr/qBittorrent connection status |
| `GET /api/movies`  | Cached Plex metadata overview (`?refresh=1` to rebuild cache) |
| `GET /api/movies/<rating_key>` | Detailed metadata for a movie; add `?refresh=1` for live ffprobe |
| `POST /actions/scan`| Trigger full scan (`operation=scan` or `verify`)     |
| `POST /actions/monitor` | Start/stop monitor (`action=start|stop`)        |
| `POST /actions/ipt-fetch` | Force an IPTorrents fetch via FlareSolverr   |
| **Download Management** ⭐ **NEW** | |
| `GET /api/download/pending` | List pending download approvals |
| `GET /api/download/active` | List active qBittorrent torrents in FEL category |
| `GET /api/download/history` | Download history (approved/declined/expired) |
| `POST /api/download/approve` | Approve pending download (adds to qBittorrent) |
| `POST /api/download/decline` | Decline pending download |
| `POST /telegram/webhook` | Telegram webhook for inline button callbacks |
| **Settings Management** ⭐ **NEW** | |
| `GET/POST /api/settings` | Get or update main settings |
| `GET/POST /api/radarr/settings` | Get or update Radarr configuration |
| `GET/POST /api/qbittorrent/settings` | Get or update qBittorrent configuration |
| `GET/POST /api/settings/notifications` | Get or update notification rules |
| `POST /api/radarr/test-connection` | Test Radarr connection |
| `POST /api/qbittorrent/test-connection` | Test qBittorrent connection |

## Requirements

- Python 3.9+ (tested on macOS/Linux)
- Node.js 18+ (for IPT monitor scripts)
- FFmpeg's `ffprobe` binary available on PATH (or configure `FFPROBE_PATH`)
- Plex server reachable via URL/token
- FlareSolverr ≥ v3 (Chromium solving Cloudflare) exposed to FELScanner
- IPTorrents cookies (`uid`, `pass`) with active account
- **For Download Approval System** ⭐ **NEW** (optional but recommended):
  - qBittorrent 4.1+ with Web UI enabled (default port 8080)
  - Radarr v3+ with API access (for path mapping)
  - Telegram Bot Token (create via @BotFather)
  - Telegram Chat ID (your personal chat or group)

## Installation & Setup

### 1. Clone repository
```bash
git clone https://github.com/rohanpandula/FELScanner.git
cd FELScanner
```

### 2. Python environment
```bash
python3 -m venv .venv
source .venv/bin/activate
PIP_USER=false pip install -r requirements.txt
```

### 3. IPTorrents Node modules
```bash
cd iptscanner
npm install
cd ..
```

### 4. Provide credentials

Either export environment vars or create `.env` (keys mirror `.env.example`):
```bash
export PLEX_URL="http://10.0.0.104:32400"
export PLEX_TOKEN="DyEmuNtvXz29zQFqGrHn"
export LIBRARY_NAME="Movies"
export FFPROBE_PATH="/usr/local/bin/ffprobe"
export IPT_UID="<ipt uid>"
export IPT_PASS="<ipt pass>"
export FLARESOLVERR_URL="http://localhost:8191"
```

If using `.env`, run `dotenv run` or ensure your process manager loads it.

### 5. Launch FlareSolverr
```bash
docker run -d --name flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest
```

### 6. Start FELScanner
```bash
PIP_USER=false FLASK_APP=app .venv/bin/python -m flask run --host=0.0.0.0 --port=5555
```
Visit `http://127.0.0.1:5555/` for the Vue dashboard. Legacy views remain at `/dashboard`, `/settings`, `/iptscanner`, `/reports`.

### 7. Configure Download Approval System ⭐ NEW (optional)

Navigate to **Settings** (gear icon in dashboard) and configure:

**Connections Tab:**
- **Radarr**: URL (e.g., `http://10.0.0.63:7878`), API Key, Root Folder Path (must match qBittorrent)
- **qBittorrent**: Host, Port (8080), Username/Password (if auth enabled), Test connections

**Notifications Tab** - Configure 17 granular rules:
- Profile 7 FEL notifications (from P5, from HDR, duplicates)
- Dolby Vision notifications (from HDR, profile upgrades)
- Atmos notifications (only if no Atmos, with DV upgrade)
- Resolution upgrades, library-only filtering
- Approval expiry time (default: 24 hours)

**Downloads Tab:**
- qBittorrent category (e.g., `movies-fel`)
- Pause on add, sequential download settings

**Set Telegram Webhook:**
After configuring Telegram in settings, set the webhook URL:
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-felscanner-domain.com/telegram/webhook"
```

For local testing with ngrok:
```bash
ngrok http 5555
# Use the https URL from ngrok
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://abc123.ngrok.io/telegram/webhook"
```

### 8. Node monitor (optional)
For continuous IPT polling outside of Flask:
```bash
cd iptscanner
node monitor-iptorrents.js
```

## Dashboard Guide

- **Library snapshot** – total DV/FEL/Atmos counts with percent-of-library badges.
- **Recent DV additions** – top eight titles (profile, Atmos, FEL, bitrate, file size).
- **Metadata Explorer** – cached Plex metadata list with live ffprobe detail on selection, Dolby Vision/Atmos/resolution filters, and per-version stream breakdowns sourced from Plex XML and ffprobe.
- **Atmos & FEL insights** – overlap numbers, average DV bitrate and file size.
- **Monitor controls** – buttons to scan, verify collections, start/stop monitor, and force IPT fetch.
- **Smart Connections Panel** – real-time health monitoring with automatic periodic checks:
  - **Plex**: Checked every 10 minutes, shows movie count and last check time
  - **Telegram**: Checked hourly, displays bot name and status
  - **qBittorrent**: Checked every 15 minutes, shows torrent count and version
  - **Radarr**: Checked every 15 minutes, shows connection status
  - **IPTorrents**: Shows time until next scheduled scan and 24h torrent delta
  - **One-click Connect**: For disconnected services, click "Connect" to attempt automatic connection
- **Pending Approvals** ⭐ **NEW** – torrents awaiting your approval:
  - Shows movie title, torrent name, upgrade type, file size
  - Request time and expiration countdown
  - Approve/Decline buttons (or use Telegram inline buttons)
  - Auto-refreshes when new approvals arrive
- **Active Downloads** ⭐ **NEW** – live qBittorrent progress tracking:
  - Real-time progress bars with percentage
  - Download speed and ETA
  - Status badges (Downloading, Paused, Seeding, etc.)
  - Downloaded/Total size display
- **Settings Panel** – dedicated tabbed page (`/settings`) for all service configuration:
  - **Connections**: Plex, Telegram, Radarr, qBittorrent with test buttons
  - **Notifications**: 17 granular notification rules
  - **Downloads**: qBittorrent behavior settings
  - **Advanced**: Collections, scanning automation, report retention
- **Yearly growth** – normalized bar list of DV additions by year.
- **IPTorrents cache** – table of cached torrents (title, size, seeds/leechers, relative added).

## Technical Notes

- **SQLite schema** is in `exports/movie_database.db` (table `movies` with `extra_data` JSON). `_compute_dolby_metrics()` runs SQL aggregates to populate the dashboard metrics.
- **Metadata cache** lives at `metadata-cache.json` by default (override via `METADATA_CACHE_FILE`). `/api/movies` serves cached summaries; `/api/movies/<rating_key>?refresh=1` runs ffprobe using `FFPROBE_PATH` and updates the cache.
- **Tailwind CSS** is loaded from CDN; Jinja variables are wrapped in `{% raw %}` to avoid Vue template conflicts.
- **Vue 3 Composition API** is bundled inline via CDN (no build step). Chart.js is also CDN-loaded.
- **Auto refresh** polls status/connections every 15 s; manual refresh hits `/api/metrics`,`/api/reports`,`/api/iptscanner/torrents`.
- **IPT fetch** leverages `iptradar/fetch-once.js` (axios + cheerio) invoked from Flask via `subprocess`, writing normalized results to `latest_results.json` and updating config caches for cookies/user agent.
- **Download tracking** uses two SQLite tables in `data/downloads.db`: `pending_downloads` (awaiting approval with expiration timestamps) and `download_history` (approved/declined/expired records with full audit trail).
- **Async integration clients** (`QBittorrentClient`, `RadarrClient`) use `aiohttp` for non-blocking API calls; Flask routes invoke them via `asyncio.run()` for synchronous context compatibility.
- **Telegram webhook** (`/telegram/webhook`) validates HMAC signatures, processes inline button callbacks (approve/decline), and delegates to `DownloadManager` methods.
- **Upgrade detection** logic in `upgrade_detector.py` compares IPT torrent metadata against Plex library using profile mapping (P5→P7 FEL, HDR→DV), resolution parsing (1080p→2160p), and audio track scanning (Atmos detection).
- **Path mapping** via Radarr API resolves movie folder paths; `DownloadManager` instructs qBittorrent to save torrents to same directory as existing Plex file for automatic version stacking.
- **Legacy templates** (`dashboard.html`, etc.) remain for backward compatibility and as reference while the new GUI evolves.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Blank dashboard (dark background only) | Hard refresh (Ctrl/Cmd + Shift + R) to bust cached Tailwind/Vue assets. Ensure `static/js/newgui-app.js` is served (check browser console).
| IPTorrents status "Cookies not configured" | Update UID/pass in IPT settings (legacy `/iptscanner`) or `.env`. Confirm FlareSolverr URL is reachable.
| FlareSolverr errors | Restart container, check logs (`docker logs flaresolverr`). Ensure solver version supports Chromium downloads.
| `movie_database.db` missing | Run a full scan (`POST /actions/scan`). Metrics require at least one completed scan.
| Plex scan stuck | Verify Plex URL/token; run `./check-plex.sh` for connectivity test.

## Contributing

- Run `flake8`/`black` for Python and `eslint` (if configured) for JS before PRs.
- Keep commits focused; document UI changes with before/after context.
- Feature branches should target `newgui` until the redesign merges back to `main`.

## License

MIT © 2025 Rohan Pandula

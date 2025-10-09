# FELScanner (newgui branch)

FELScanner is a Dolby Vision/TrueHD intelligence layer for Plex. It crawls your library, curates collections, produces detailed reports, and now ships with a Vue/Tailwind control center that surfaces live Dolby Vision metrics, Atmos coverage, and IPTorrents discoveries at a glance.

## Key Capabilities

- **Plex Dolby Vision Profiler** – classifies every movie by Dolby Vision profile (highlighting Profile 7 FEL), FEL/MEL status, and Atmos availability.
- **Smart Collections** – keeps Plex collections (All DV, FEL, Atmos) in sync based on scan results with one-click verify & repair.
- **Insight Dashboard (Vue + Tailwind)** – the landing page (`/`) shows live scan status, DV/Atmos ratios, FEL overlaps, yearly growth trends, recent additions, connection health, and cached IPTorrents hits.
- **Detailed Exports** – generates JSON/CSV snapshots (`exports/`) with per-title metadata including bitrate, file size, and audio tracks.
- **FlareSolverr-powered IPTorrents Monitor** – polls IPTorrents via FlareSolverr, tracks new FEL releases, and exposes cached results to the dashboard.
- **REST endpoints for automation** – JSON APIs expose scan state, rich DV metrics, report manifests, and connection telemetry for external tooling.

## Architecture Overview

```
FELScanner (Flask)
├── app.py                 # Flask routes, background jobs, REST endpoints
├── scanner.py             # Plex scanning engine, SQLite persistence
├── templates/
│   ├── index.html         # Vue/Tailwind single-page control center
│   ├── dashboard.html     # Legacy dashboard view
│   ├── settings.html      # Legacy settings view
│   └── iptscanner.html    # Legacy IPTorrents settings
├── static/js/
│   ├── newgui-app.js      # Vue app powering the new control center
│   └── main.js            # Legacy dashboard interactions
├── iptscanner/
│   ├── fetch-once.js      # FlareSolverr one-shot fetch
│   ├── monitor-iptorrents.js # Background monitor (Node.js)
│   └── package.json       # Node dependencies (axios, cheerio, cron, sqlite3)
└── exports/, data/        # Generated reports, SQLite movie DB
```

### Backend data flow

1. `scanner.PlexDVScanner` walks your Plex movie library via PlexAPI, captures profile/Atmos metadata, and stores results in `exports/movie_database.db`.
2. REST helpers in `app.py` compute roll-up metrics (profile distribution, FEL/Atmos overlaps, growth by year, quality averages) and expose them under `/api/metrics`.
3. `/api/status` reports scan/monitor state and last collection changes; `/api/connections` summarizes Plex/IPT/Telegram health.
4. IPTorrents fetches flow through `run_ipt_scanner()` → `iptradar/fetch-once.js` → FlareSolverr → cached JSON under `iptscanner/data/latest_results.json`.

### New REST endpoints

| Endpoint            | Description                                          |
|---------------------|------------------------------------------------------|
| `GET /api/status`   | Scan/monitor state plus last DV/Atmos counts         |
| `GET /api/metrics`  | Dolby Vision analytics (profiles, overlaps, quality) |
| `GET /api/reports`  | Recent report manifest (filename, timestamp, size)   |
| `GET /api/connections` | Plex/IPT/Telegram connection status               |
| `POST /actions/scan`| Trigger full scan (`operation=scan` or `verify`)     |
| `POST /actions/monitor` | Start/stop monitor (`action=start|stop`)        |
| `POST /actions/ipt-fetch` | Force an IPTorrents fetch via FlareSolverr   |

## Requirements

- Python 3.9+ (tested on macOS/Linux)
- Node.js 18+ (for IPT monitor scripts)
- Plex server reachable via URL/token
- FlareSolverr ≥ v3 (Chromium solving Cloudflare) exposed to FELScanner
- IPTorrents cookies (`uid`, `pass`) with active account

## Installation & Setup

### 1. Clone and branch
```bash
git clone https://github.com/rohanpandula/FELScanner.git
cd FELScanner
git checkout newgui
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

### 7. Node monitor (optional)
For continuous IPT polling outside of Flask:
```bash
cd iptscanner
node monitor-iptorrents.js
```

## Dashboard Guide (new GUI)

- **Library snapshot** – total DV/FEL/Atmos counts with percent-of-library badges.
- **Recent DV additions** – top eight titles (profile, Atmos, FEL, bitrate, file size).
- **Profile distribution (Chart.js)** – doughnut chart of DV profile mix with light/dark toggle.
- **Atmos & FEL insights** – overlap numbers, average DV bitrate and file size.
- **Monitor controls** – buttons to scan, verify collections, start/stop monitor, and force IPT fetch.
- **Connections** – real-time status for Plex, IPTorrents (last/next sync, 24h delta), Telegram, API server.
- **Yearly growth** – normalized bar list of DV additions by year.
- **Recent reports** – quick access to generated JSON/CSV (download via `/reports`).
- **IPTorrents cache** – table of cached torrents (title, size, seeds/leechers, relative added).

## Technical Notes

- **SQLite schema** is in `exports/movie_database.db` (table `movies` with `extra_data` JSON). `_compute_dolby_metrics()` runs SQL aggregates to populate the dashboard metrics.
- **Tailwind CSS** is loaded from CDN; Jinja variables are wrapped in `{% raw %}` to avoid Vue template conflicts.
- **Vue 3 Composition API** is bundled inline via CDN (no build step). Chart.js is also CDN-loaded.
- **Auto refresh** polls status/connections every 15 s; manual refresh hits `/api/metrics`,`/api/reports`,`/api/iptscanner/torrents`.
- **IPT fetch** leverages `iptradar/fetch-once.js` (axios + cheerio) invoked from Flask via `subprocess`, writing normalized results to `latest_results.json` and updating config caches for cookies/user agent.
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

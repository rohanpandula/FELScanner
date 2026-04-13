# FELScanner

> Dolby Vision intelligence layer for Plex. Detects DV profiles, FEL layers, TrueHD Atmos, and HDR formats across your library, then tells you what to upgrade, what's duplicated, and where your disk is going.

Built for collectors who care about the difference between Profile 5 and Profile 7.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Development](#development)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Security](#security)
- [License](#license)

---

## Features

- **Library scanning.** Walks your entire Plex library and identifies every movie's video profile (DV P5/P7/P8, HDR10, SDR), audio format (TrueHD Atmos, DTS-HD MA, AC3), resolution, codec, and HDR metadata.
- **Storage analytics.** AntV-rendered treemap by DV status, donut by resolution, top-10 largest files, plus breakdowns by audio and codec.
- **Quality report.** Health score out of 100, tier pie (Reference → Excellent → Good → Needs-Upgrade), radar across DV / FEL / Atmos / 4K coverage.
- **Upgrade detection.** Scrapes IPTorrents for P7 FEL releases, matches titles against your Plex library and Radarr catalogue, flags candidates.
- **One-click approval.** Telegram inline buttons or web UI; approved downloads go straight to qBittorrent and Radarr.
- **Duplicate detection.** Finds movies with multiple versions and lets you compare them side-by-side.
- **Release-group intelligence.** Tracks encode quality per group; prefer or block groups.
- **Activity timeline.** Every scan, download, and library change chronologically.
- **ffprobe explorer.** Deep dive into streams, containers, and side-data for any title.
- **Live scan log.** Server-sent events stream progress from Plex discovery through collection updates.

## Architecture

```
Frontend (Vue 3 + TypeScript, Geist/zinc design, AntV charts)
    |
    v
API (FastAPI + async Python, APScheduler, in-process IPT scraper)
    |
    v
Storage (Postgres 15 + Redis 7 in one image via tini + su-exec)
    |
    +--> Plex API       (library metadata, collections)
    +--> qBittorrent    (download management)
    +--> Radarr         (movie path resolution, add movies)
    +--> Telegram Bot   (notifications, inline approvals)
    +--> FlareSolverr   (Cloudflare bypass for IPTorrents)
    '--> AntV GPT-Vis   (server-rendered storytelling charts)
```

**Three containers:** `api`, `frontend`, `storage`. FlareSolverr is treated as an external dependency — point `FLARESOLVERR_URL` at any existing instance on your network.

## Prerequisites

- Docker 24+ and Docker Compose v2
- Plex Media Server with a movie library
- qBittorrent *(optional — for auto-downloads)*
- Radarr *(optional — for auto-add)*
- IPTorrents account *(optional — for upgrade detection)*
- FlareSolverr reachable from the api container *(required only if using IPTorrents)*

## Installation

```bash
git clone https://github.com/rohanpandula/fel-syncer.git felscanner
cd felscanner

cp .env.example .env
# Edit .env — at minimum set PLEX_URL, PLEX_TOKEN, LIBRARY_NAME.

cd docker
docker compose up -d
```

The UI is served on `http://<your-host>:5173` by default. Adjust `FRONTEND_PORT` in `.env` to change.

## Configuration

All runtime config lives in `.env`. On first boot the app seeds a `settings` row in Postgres from your env vars so the in-app Settings screen isn't blank.

### Required

| Variable | Description |
|----------|-------------|
| `PLEX_URL` | Plex server URL (e.g. `http://plex.lan:32400`) |
| `PLEX_TOKEN` | Plex auth token ([find yours](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)) |
| `LIBRARY_NAME` | Plex movies library name (default `Movies`) |

### Optional feature toggles

| Variable | Enables |
|----------|---------|
| `TELEGRAM_TOKEN` + `TELEGRAM_CHAT_ID` | Push notifications + inline approvals |
| `RADARR_URL` + `RADARR_API_KEY` | Movie path resolution, auto-add missing titles |
| `QBITTORRENT_HOST` + `QBITTORRENT_USERNAME` + `QBITTORRENT_PASSWORD` | Download dispatch |
| `IPT_UID` + `IPT_PASS` + `IPT_CF_CLEARANCE` | IPTorrents credentials (session cookies) |
| `FLARESOLVERR_URL` | Cloudflare bypass URL (e.g. `http://flaresolverr:8191`) |
| `SCAN_FREQUENCY_HOURS` | Override the scheduled full-scan interval |

See `.env.example` for every variable with descriptions.

### Running alongside Plex on Unraid macvlan

If Plex, Radarr, and qBittorrent live on a custom Docker network with their own LAN IPs (common on Unraid with `br0` macvlan), the default bridge network can't reach them through the host. Uncomment the `br0:` block in `docker/docker-compose.yml` under the `api` service and set `API_BR0_IP` in `.env` to a free IP on that LAN. The api container dual-homes to both the internal bridge (for Postgres/Redis) and your LAN bridge (for Plex). Inline comments in the compose file walk through the specifics.

## Usage

Once the stack is running:

1. Open `http://<your-host>:5173`
2. Click **Start Scan** on the Dashboard to trigger a library walk. The scan log streams live progress.
3. Explore:
   - `/storage` — where your disk is going
   - `/quality` — library health score + tier breakdown
   - `/insights` — duplicates and upgrade opportunities
   - `/downloads` — pending approvals + active transfers
   - `/ipt` — IPTorrents results matched against your library

Scheduled scans run automatically on the interval set by `SCAN_FREQUENCY_HOURS` (default 24).

### Pages

| Page | Path | Contents |
|------|------|----------|
| Dashboard | `/` | Library stats, scan controls, live log, pending approvals |
| Quality Report | `/quality` | Health score, tier donut, DV/FEL/Atmos/4K radar |
| Insights | `/insights` | Upgrade opportunities, duplicate groups |
| Storage | `/storage` | Treemap by DV status, donut by resolution, top-10 files |
| Metadata Explorer | `/metadata` | ffprobe drill-down per movie |
| Downloads | `/downloads` | Pending approvals, active transfers, audit trail |
| IPT Scanner | `/ipt` | IPTorrents results enriched with library match info |
| Release Groups | `/groups` | Group-level stats; mark groups as preferred or blocked |
| Activity Feed | `/activity` | Timeline of scans, downloads, library changes |
| Settings | `/settings` | Connection health, notification rules, collections, scan schedule |

## Development

Run each service outside Docker for fast iteration.

### Backend (FastAPI)

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Requires a reachable Postgres + Redis. Either point at the Dockerized `storage` container or export `DATABASE_URL` / `REDIS_URL` for a local install.

### Frontend (Vue 3)

```bash
cd services/frontend
npm install
npm run dev                     # Vite HMR at :5173
npm run build                   # production build
npm run build:check             # build with TypeScript strict check
```

### Full stack (dev compose)

```bash
cd docker
docker compose -f docker-compose.dev.yml up -d
docker compose logs -f api
```

### Common commands

```bash
# Type-check and lint backend
cd services/api
mypy app/
flake8 app/ tests/
black app/ tests/
isort app/ tests/

# Frontend
cd services/frontend
npm run lint
npm run format
```

## Testing

### Backend (pytest)

```bash
cd services/api
pytest                              # all tests
pytest --cov=app --cov-report=html  # with coverage
pytest -m unit                      # unit tests only
pytest -m integration               # integration tests only
pytest tests/unit/test_torrent_parser.py   # single file
```

Test fixtures live in `tests/conftest.py`. Integration tests require a running Postgres; point `DATABASE_URL` at a test database or use the Docker stack.

### Frontend

```bash
cd services/frontend
npm run test:unit       # Vitest unit tests
npm run test:e2e        # Playwright end-to-end
```

## Project Structure

```
felscanner/
├── docker/
│   ├── docker-compose.yml          # Prod stack (3 containers)
│   ├── docker-compose.dev.yml      # Dev overrides
│   └── storage/
│       ├── Dockerfile              # Postgres 15 + Redis 7 combined image
│       └── run.sh                  # Runtime supervisor
├── database/
│   └── init.sql                    # Initial schema
├── services/
│   ├── api/                        # FastAPI backend (Python 3.11)
│   │   ├── app/
│   │   │   ├── api/v1/             # REST endpoints
│   │   │   ├── core/               # Config, DB, logging, seed
│   │   │   ├── integrations/       # Plex, qBittorrent, Radarr, Telegram
│   │   │   ├── models/             # SQLAlchemy ORM
│   │   │   ├── services/           # Business logic + in-process IPT scraper
│   │   │   └── tasks/              # APScheduler periodic jobs
│   │   └── tests/                  # pytest unit + integration
│   └── frontend/                   # Vue 3 + Vite
│       └── src/
│           ├── api/                # Axios clients
│           ├── components/         # Reusable components + AntVChart
│           ├── composables/        # Including useAntVChart
│           ├── stores/             # Pinia state
│           └── views/              # Top-level pages
├── scripts/                        # Utility scripts (migration, etc.)
└── README.md
```

## Security

- Secrets are read from `.env` (gitignored) or env vars at runtime. No hardcoded tokens anywhere in the repo.
- GitHub secret-scanning push protection is enabled on the remote.
- Plex / Telegram / qBittorrent / Radarr credentials are stored only in the Postgres `settings` table (seeded from env on first boot) for the UI to read back.
- The api container exposes only `/health` publicly; every other endpoint requires the internal bridge network or the frontend nginx proxy.

## License

MIT.

# FELScanner

Dolby Vision intelligence layer for Plex. Detects DV profiles, FEL layers, TrueHD Atmos, and HDR formats across your entire library — then helps you find and download upgrades.

Built for collectors who care about the difference between Profile 5 and Profile 7.

## What it does

- **Library scanning** — Scans your Plex library and identifies every movie's video profile (DV P5/P7/P8, HDR10, SDR), audio format (TrueHD Atmos, DTS-HD MA, AC3), and resolution
- **Quality dashboard** — Visual breakdown of your library: how many movies have DV, FEL, Atmos, 4K. A report card for your collection
- **Upgrade detection** — Cross-references your library against IPTorrents to find P7 FEL releases for movies you already own
- **One-click downloads** — Download upgrades directly from the UI via qBittorrent + Radarr integration. Movies not in Radarr get added automatically
- **Storage analytics** — Storage breakdown by resolution, DV status, audio codec, and video codec. See your largest files and average sizes per quality tier
- **Duplicate management** — Find movies with multiple versions and compare them side-by-side
- **Release group tracking** — Track which release groups produce the best encodes across your library
- **Activity feed** — Timeline of scans, downloads, and library changes
- **ffprobe metadata explorer** — Deep dive into any movie's streams, codecs, and container metadata
- **Telegram notifications** — Get notified when new P7 FEL releases appear, with inline approve/decline buttons

## Architecture

```
Frontend (Vue 3 + TypeScript)
    |
    v
API (FastAPI + async Python)
    |
    |--> PostgreSQL (library data, scan history, download tracking)
    |--> Redis (caching, job queue)
    |-->  Plex API (library metadata, collections)
    |--> qBittorrent API (download management)
    |--> Radarr API (movie path resolution, add movies)
    |--> Telegram Bot API (notifications, approvals)
    '--> IPT Scraper (Node.js + Puppeteer)
             |
             '--> FlareSolverr (Cloudflare bypass)
```

**6 Docker services:** API, Frontend, PostgreSQL, Redis, IPT Scraper, FlareSolverr

## Quick start

### Prerequisites

- Docker + Docker Compose
- Plex Media Server with a movie library
- qBittorrent (for downloads)
- Radarr (for movie management)
- IPTorrents account (for torrent search)

### Setup

```bash
git clone https://github.com/rohanpandula/FELScanner.git
cd FELScanner

# Copy and edit environment config
cp .env.example .env
# Fill in your Plex token, Radarr API key, qBittorrent URL, etc.

# Start everything
cd docker
docker-compose up -d
```

The UI will be available at `http://your-server:80` (nginx) or `http://your-server:5173` (direct frontend).

### Configuration

All configuration is done via environment variables in `.env`. See `.env.example` for all available options with descriptions.

Key settings:

| Variable | Description |
|----------|-------------|
| `PLEX_URL` | Your Plex server URL (e.g., `http://10.0.0.100:32400`) |
| `PLEX_TOKEN` | Plex authentication token |
| `LIBRARY_NAME` | Plex library name to scan (default: `Movies`) |
| `RADARR_URL` | Radarr instance URL |
| `RADARR_API_KEY` | Radarr API key |
| `QBITTORRENT_HOST` | qBittorrent WebUI host |
| `TELEGRAM_TOKEN` | Telegram bot token (optional) |
| `IPT_UID` / `IPT_PASS` | IPTorrents credentials |

## Tech stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy (async), APScheduler
- **Frontend:** Vue 3, TypeScript, Vite, Pinia, Tailwind CSS
- **Database:** PostgreSQL with JSONB fields and GIN indexes
- **Cache:** Redis
- **Scraper:** Node.js, Puppeteer, Express
- **Infrastructure:** Docker Compose, Nginx

## Development

```bash
# Backend
cd services/api
pip install -r requirements.txt
pytest                    # run tests
black app/ tests/         # format
mypy app/                 # type check

# Frontend
cd services/frontend
npm install
npm run dev               # dev server with HMR
npm run build             # production build
npm run test:unit         # unit tests

# Full stack (Docker)
cd docker
docker-compose -f docker-compose.dev.yml up -d
```

## Pages

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | Library stats, scan controls, connection status |
| Quality Report | `/quality` | DV profile, resolution, audio distribution charts |
| Insights | `/insights` | Upgrade opportunities, duplicate detection |
| Storage | `/storage` | Storage breakdown by every dimension |
| Metadata Explorer | `/metadata` | ffprobe deep dive into any movie |
| Downloads | `/downloads` | Download approval queue and history |
| IPT Scanner | `/ipt` | Browse IPT releases with library matching |
| Release Groups | `/groups` | Release group stats across your library |
| Activity Feed | `/activity` | Timeline of all scans and downloads |
| Settings | `/settings` | Connection config, scan schedules, notifications |

## License

MIT

# FELScanner

Dolby Vision intelligence layer for Plex. Scans your library for DV profiles, FEL layers, TrueHD Atmos, and HDR formats — then tells you what to upgrade, what's duplicated, and where your disk is going.

Built for collectors who care about the difference between Profile 5 and Profile 7.

## What it does

- **Library scanning** — Full-library scan against Plex identifies every movie's video profile (DV P5/P7/P8, HDR10, SDR), audio format (TrueHD Atmos, DTS-HD MA, AC3), resolution, codec, and HDR metadata.
- **Storage analytics** — Treemap by DV status, donut by resolution, top-10 largest files, breakdowns by audio + codec. "Unknown" rows pruned, sorted by bytes descending.
- **Quality report** — Health score out of 100, tier pie (Reference → Excellent → Good → Needs-Upgrade), radar across DV / FEL / Atmos / 4K coverage.
- **Upgrade detection** — Scrapes IPTorrents for P7 FEL releases, cross-matches titles against your Plex library and Radarr catalogue, flags candidates.
- **One-click approval** — Telegram inline buttons or web UI; approved downloads get sent straight to qBittorrent and Radarr.
- **Duplicate detection** — Find movies with multiple versions (e.g., 1080p + 4K of the same film) and compare side-by-side.
- **Release-group intelligence** — Track which groups produce the best encodes. Prefer/block individual groups.
- **Activity timeline** — Every scan, download, and library change, chronologically.
- **ffprobe explorer** — Drill into any movie's streams, containers, side-data — subtitle tracks, HDR10+ metadata, frame rate, bit depth.

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

**Three containers:** `api`, `frontend`, `storage`. FlareSolverr runs externally — point `FLARESOLVERR_URL` at any existing instance on your network.

## Quick start

### Prerequisites

- Docker + Docker Compose
- Plex Media Server with a movie library
- qBittorrent (optional — for auto-downloads)
- Radarr (optional — for auto-add)
- IPTorrents account (optional — for upgrade detection)
- FlareSolverr reachable from the api container (Cloudflare bypass)

### Setup

```bash
git clone https://github.com/rohanpandula/fel-syncer.git felscanner
cd felscanner

cp .env.example .env
# Edit .env — fill in PLEX_URL, PLEX_TOKEN, LIBRARY_NAME at minimum.

cd docker
docker compose up -d
```

The UI is available at `http://<your-host>:5173` (or whatever you set `FRONTEND_PORT` to). It proxies all `/api/*` traffic to the backend over the internal bridge network.

### Configuration

All runtime config is via `.env`. The app also seeds a settings row in the database on first boot (from your env vars) so the Settings UI isn't blank.

Minimum env vars to run:

| Variable | Description |
|----------|-------------|
| `PLEX_URL` | Plex server URL (e.g. `http://plex.lan:32400`) |
| `PLEX_TOKEN` | Plex auth token ([how to find it](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)) |
| `LIBRARY_NAME` | Plex movies library name (default `Movies`) |

Optional (adds features):

| Variable | Description |
|----------|-------------|
| `TELEGRAM_TOKEN` + `TELEGRAM_CHAT_ID` | Push notifications + inline approvals |
| `RADARR_URL` + `RADARR_API_KEY` | Movie path resolution, auto-add missing titles |
| `QBITTORRENT_HOST` + `QBITTORRENT_USERNAME` + `QBITTORRENT_PASSWORD` | Download dispatch |
| `IPT_UID` + `IPT_PASS` + `IPT_CF_CLEARANCE` | IPTorrents credentials (cookies) |
| `FLARESOLVERR_URL` | Cloudflare bypass URL (e.g. `http://flaresolverr:8191`) |

See `.env.example` for every variable with descriptions.

### Running alongside other Plex-adjacent containers (Unraid macvlan)

If Plex / Radarr / qBittorrent live on a custom Docker network with their own LAN IPs (common on Unraid with `br0` macvlan), the default bridge network can't reach them through the host. In that case, uncomment the `br0:` block in `docker/docker-compose.yml` under the `api` service and set `API_BR0_IP` in `.env` to a free IP on that LAN. The api container dual-homes to both the internal bridge (for Postgres/Redis) and your LAN bridge (for Plex). Details are in the inline comments in the compose file.

## Tech stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy (async), APScheduler, httpx
- **Frontend:** Vue 3, TypeScript, Vite, Pinia, Tailwind CSS, Geist font, AntV GPT-Vis charts
- **Storage:** Postgres 15 + Redis 7 bundled into one image (tini supervisor)
- **IPT scraper:** Python port using httpx + BeautifulSoup, relies on an external FlareSolverr
- **Infrastructure:** Docker Compose

## Development

```bash
# Backend
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pytest                  # run tests

# Frontend
cd services/frontend
npm install
npm run dev             # Vite dev server with HMR at :5173
npm run build           # production build
npm run test:unit       # Vitest

# Full stack
cd docker
docker compose up -d
docker compose logs -f api
```

## Pages

| Page | Path | What it shows |
|------|------|---------------|
| Dashboard | `/` | Library stats, scan controls, scan log stream, pending approvals |
| Quality Report | `/quality` | Health score, tier donut, DV/FEL/Atmos/4K radar |
| Insights | `/insights` | Upgrade opportunities, duplicate groups |
| Storage | `/storage` | Treemap by DV status, pie by resolution, top-10 largest files |
| Metadata Explorer | `/metadata` | ffprobe drill-down per movie |
| Downloads | `/downloads` | Pending approvals, active transfers, audit trail |
| IPT Scanner | `/ipt` | IPTorrents results enriched with library match info |
| Release Groups | `/groups` | Group-level stats; mark groups as preferred or blocked |
| Activity Feed | `/activity` | Timeline of scans, downloads, library changes |
| Settings | `/settings` | Connection health, notification rules, collections, scan schedule |

## Design

The UI follows a single-accent (electric blue `#4d7cff`) dark theme on a zinc-950 base, Geist sans + Geist Mono typography, flat weight-based hierarchy. No AI purple gradients, no generic three-column card rows, no gradient text on headers.

Data storytelling uses AntV GPT-Vis charts (treemap, donut, radar, sankey) served through a proxy endpoint so the browser doesn't hit CORS.

## Security

- Every secret comes from `.env` (gitignored) or env vars at runtime. No hardcoded tokens anywhere in the repo.
- Plex / Telegram / qBittorrent / Radarr credentials are only read at runtime and stored to the Postgres `settings` table on first boot for the UI to read.
- The api container opens only `/health` publicly — everything else requires the internal bridge network or the frontend nginx proxy.

## License

MIT

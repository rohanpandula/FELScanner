# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

FELScanner v2 is a Dolby Vision/TrueHD intelligence layer for Plex that detects DV profiles (especially P7 FEL), manages upgrades, and integrates with download clients. It's a complete architectural refactor from v1 using:

- **Backend**: FastAPI (async Python 3.11+), PostgreSQL, Redis, APScheduler
- **Frontend**: Vue 3 + TypeScript + Vite + Pinia
- **Microservices**: IPT scraper (Node.js + Puppeteer + Express)
- **Infrastructure**: Docker Compose with 6 services

## Development & Deployment Strategy

**All services run in Docker.** This project is designed to be deployed on a NAS and should always be developed and tested using Docker Compose.

```bash
# Start all services (from docker/ directory)
cd docker
docker-compose up -d

# View logs
docker-compose logs -f

# Rebuild after code changes
docker-compose build && docker-compose up -d
```

Do NOT run services locally outside of Docker. The inter-service communication (API → IPT scraper, API → Redis, etc.) relies on Docker network hostnames like `ipt-scraper:3000`, `postgres:5432`, and `redis:6379`.

## Common Development Commands

### Backend (FastAPI)

```bash
cd services/api

# Install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run development server with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run all tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_scan_service.py

# Run tests with markers
pytest -m unit          # Only unit tests
pytest -m integration   # Only integration tests
pytest -m "not slow"    # Skip slow tests

# Code formatting
black app/ tests/
isort app/ tests/

# Type checking
mypy app/

# Linting
flake8 app/ tests/
```

### Frontend (Vue 3)

```bash
cd services/frontend

# Install dependencies
npm install

# Run development server (with HMR at http://localhost:5173)
npm run dev

# Build for production
npm run build

# Build with TypeScript checking
npm run build:check

# Preview production build
npm run preview

# Run unit tests
npm run test:unit

# Run E2E tests (Playwright)
npm run test:e2e

# Lint and fix
npm run lint

# Format code
npm run format
```

### IPT Scraper (Node.js)

```bash
cd services/ipt-scraper

# Install dependencies
npm install

# Run development server with nodemon
npm run dev

# Run production server
npm start

# Run tests
npm test
```

### Docker

```bash
# Start all services (from root or docker/)
cd docker
docker-compose up -d

# Start with dev configuration
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose logs -f api
docker-compose logs -f ipt-scraper

# Rebuild specific service
docker-compose build api
docker-compose up -d api

# Stop all services
docker-compose down

# Stop and remove volumes (destructive)
docker-compose down -v
```

### Database

```bash
# Connect to PostgreSQL
docker exec -it felscanner-postgres psql -U felscanner -d felscanner

# Run SQL file
docker exec -i felscanner-postgres psql -U felscanner -d felscanner < database/init.sql

# Backup database
docker exec felscanner-postgres pg_dump -U felscanner felscanner > backup.sql

# Check table counts
docker exec felscanner-postgres psql -U felscanner -d felscanner -c "SELECT COUNT(*) FROM movies;"
```

## Architecture Overview

### Service Communication Flow

```
Frontend (Vue 3) → API (FastAPI) → PostgreSQL
                                  → Redis
                                  → Plex API
                                  → qBittorrent
                                  → Radarr
                                  → Telegram
                                  → IPT Scraper → FlareSolverr
```

### Backend Structure (services/api/app/)

The FastAPI backend follows a layered architecture:

- **`core/`**: Core infrastructure components
  - `config.py`: Pydantic settings (all env vars centralized here)
  - `database.py`: SQLAlchemy async engine and session management
  - `logging.py`: Structured JSON logging with request tracing
  - `metrics.py`: Prometheus metrics collection

- **`models/`**: SQLAlchemy ORM models (database tables)
  - `movie.py`: Core movie metadata with DV profiles, audio tracks
  - `pending_download.py`: Download approval workflow
  - `download_history.py`: Audit trail for downloads
  - `scan_history.py`: Scan operation tracking
  - `settings.py`: User-configurable settings
  - `connection_status.py`: External service health checks
  - `metadata_cache.py`: ffprobe metadata caching
  - `notification_queue.py`: Telegram notification queue
  - `collection_change.py`: Plex collection change tracking

- **`schemas/`**: Pydantic models (API DTOs and validation)
  - Request/response schemas for all endpoints
  - Data validation and serialization

- **`api/v1/`**: REST API endpoints
  - `scan.py`: Scan triggering and status
  - `movies.py`: Movie listing and filtering
  - `downloads.py`: Download approval workflow
  - `metadata.py`: ffprobe metadata explorer
  - `collections.py`: Plex collection management
  - `settings.py`: Settings CRUD
  - `connections.py`: External service connection status
  - `status.py`: Application status and statistics
  - `ipt.py`: IPT scraper integration

- **`services/`**: Business logic layer
  - `scan_service.py`: Library scanning orchestration
  - `movie_service.py`: Movie data operations
  - `ipt_service.py`: IPT scraper client

- **`integrations/`**: External API clients
  - `plex/`: Plex API integration (library access, metadata)
  - `qbittorrent/`: qBittorrent client (download management)
  - `radarr/`: Radarr client (folder path resolution)
  - `telegram/`: Telegram bot handler (inline button approvals)
  - `upgrade_detector.py`: 17 notification rules for upgrade eligibility

- **`tasks/`**: Background job management
  - `scheduler.py`: APScheduler configuration (periodic scans, monitoring, cleanup)

### Database Schema

The PostgreSQL database uses:
- **JSONB fields** for flexible metadata (audio_tracks, extra_data)
- **GIN indexes** on JSONB columns for fast queries
- **Partial indexes** for commonly filtered subsets (active downloads)
- **Triggers** for auto-updating timestamps
- **Foreign keys** with appropriate cascade rules

Key tables:
- `movies`: Core Plex movie data with DV/Atmos detection
- `pending_downloads`: Download approval workflow (pending → approved/declined)
- `download_history`: Audit trail for download actions
- `scan_history`: Scan operation analytics
- `settings`: Application configuration (stored in DB, not just env)
- `connection_status`: Health check results for external services
- `metadata_cache`: ffprobe metadata cache to avoid re-parsing
- `notification_queue`: Telegram message queue for retry logic
- `collection_change`: Tracks Plex collection membership changes

### Frontend Structure (services/frontend/src/)

- **`stores/`**: Pinia state management
  - `app.ts`: Global app state (connections, scan status)
  - `movies.ts`: Movie data and filtering
  - `downloads.ts`: Download approval state
  - `metadata.ts`: Metadata explorer state
  - `settings.ts`: Settings state

- **`views/`**: Top-level page components
  - `Dashboard.vue`: Overview with statistics and recent scans
  - `Downloads.vue`: Download approval interface
  - `MetadataExplorer.vue`: ffprobe metadata viewer
  - `IPTScanner.vue`: IPT scraper control panel
  - `Settings.vue`: Configuration interface

- **`components/`**: Reusable Vue components
  - Organized by feature (MovieCard, FilterBar, StatCard, etc.)

- **`api/`**: Axios HTTP client
  - Type-safe API clients matching backend endpoints

### IPT Scraper (services/ipt-scraper/)

Isolated Node.js microservice that:
- Scrapes IPTorrents for Dolby Vision releases
- Uses Puppeteer for browser automation
- Integrates with FlareSolverr for Cloudflare bypass
- Tracks "known" torrents to only return new results
- Exposes REST API consumed by main backend

### Background Jobs (APScheduler)

The scheduler runs these periodic tasks:
1. **Connection health checks** (15 min): Verify Plex, qBittorrent, Radarr, Telegram connectivity
2. **Periodic library scans** (configurable hours): Full Plex library scan
3. **Monitor cycle** (1 min when enabled): Check for new DV additions
4. **Notification queue processing** (1 min): Process pending Telegram messages
5. **Cleanup expired downloads** (hourly): Mark expired pending downloads

### Upgrade Detection Logic

`integrations/upgrade_detector.py` implements 17 notification rules:
- FEL notifications (any FEL, P5→P7, HDR→FEL, duplicates)
- DV notifications (any DV, HDR→DV, profile upgrades)
- Atmos notifications (any Atmos, only if no Atmos, with DV combo)
- Resolution notifications (2160p, upgrades only)
- Library filtering (only notify for movies already in library)
- Expiration windows (configurable hours)

The detector parses torrent titles using regex patterns to extract:
- Resolution (2160p, 1080p, 720p)
- DV profile (P4-P9)
- FEL presence (BL+EL, P7)
- Atmos/TrueHD audio
- HDR10/HDR

### Configuration Management

Settings are managed in multiple layers:
1. **Environment variables**: `services/api/app/core/config.py` (Pydantic Settings)
2. **Database settings**: `models/settings.py` (user-configurable via UI)
3. **Docker Compose**: `docker/docker-compose.yml` (service orchestration)
4. **`.env` files**: `.env.example`, `.env.production.example`

All environment variables are centralized in `core/config.py` with:
- Type validation (Pydantic)
- Default values
- Field descriptions
- Custom validators (e.g., URL format checking)

## Testing Strategy

### Backend Tests (pytest)

- **Unit tests** (`tests/unit/`): Test individual functions/classes in isolation
- **Integration tests** (`tests/integration/`): Test with real database connections
- **E2E tests** (`tests/e2e/`): Full workflow testing

Test configuration in `pytest.ini`:
- Async mode enabled (`asyncio_mode = auto`)
- Markers for test categorization (`@pytest.mark.unit`, `@pytest.mark.slow`)
- Fixtures in `conftest.py` for database/client setup

### Frontend Tests

- **Unit tests** (Vitest): Component testing with Vue Test Utils
- **E2E tests** (Playwright): Full browser automation testing

## Key Design Patterns

### Async/Await Throughout

All I/O operations use async/await:
- Database queries (SQLAlchemy async)
- HTTP requests (aiohttp, httpx)
- Redis operations
- Plex API calls

### Dependency Injection

FastAPI dependencies for:
- Database sessions (`get_db()`)
- Settings (`get_settings()`)
- Service instances

### Service Layer Pattern

Controllers (`api/v1/`) are thin routing layers. Business logic lives in `services/`:
- Controllers handle HTTP concerns (parsing, validation, responses)
- Services contain business logic and orchestration
- Models handle data persistence

### Structured Logging

All logs use structured format with:
- JSON output in production
- Request tracing IDs
- Contextual fields (user, movie_id, scan_id, etc.)

### Prometheus Metrics

Custom metrics tracked:
- `felscanner_scan_requests_total`: Total scan requests
- `felscanner_scan_duration_seconds`: Scan duration histogram
- `felscanner_active_downloads`: Active download count
- `felscanner_movies_total{category}`: Movie counts by category (dv, p7, atmos)

## Common Gotchas

### Database Session Management

Always use dependency injection for database sessions:
```python
async def endpoint(db: AsyncSession = Depends(get_db)):
    # db session is automatically closed after request
```

Don't create sessions manually unless in background tasks.

### Async Context Managers

Plex integration uses async context managers:
```python
async with PlexClient() as plex:
    movies = await plex.get_movies()
```

### JSONB Column Access

When querying JSONB columns in SQLAlchemy:
```python
# Extract nested field
stmt = select(Movie).where(Movie.extra_data['collections'].contains(['All DV']))
```

### Auto-start Modes

The API has three auto-start modes (`AUTO_START_MODE` in settings):
- `disabled`: Manual scan trigger only
- `scan`: Full library scan on startup
- `monitor`: Start monitor mode on startup (checks for new DV every minute)

### Telegram Inline Buttons

Download approvals use Telegram inline buttons with callback data:
- Format: `approve:request_id` or `decline:request_id`
- Handler in `integrations/telegram/handler.py`

### FFProbe Integration

Metadata extraction requires ffprobe binary:
- Path configured via `FFPROBE_PATH` env var
- Results cached in `metadata_cache` table to avoid re-parsing
- Timeout configured via `FFPROBE_TIMEOUT`

## Migration from v1

If working with migration-related code:
- v1 used SQLite → v2 uses PostgreSQL
- v1 had 7 daemon threads → v2 uses APScheduler
- Migration script: `scripts/migrate-data.py`
- All v1 features preserved (60+ endpoints, 17 notification rules)

## Recent Fixes and Improvements (January 2026)

### Atmos Detection Enhancement
**File**: `services/api/app/integrations/plex/scanner.py`

Fixed Atmos detection to recognize TrueHD 8-channel tracks as Atmos:
- Previously only checked for explicit "atmos" text in metadata
- Now detects TrueHD with 8 channels (7.1 + height channels = Atmos)
- Fixes false negatives for movies like "Moana 2" that have Atmos but don't label it explicitly

```python
# TrueHD with 8 channels is Atmos (7.1 with height channels)
if codec == "truehd" and int(channels) == 8:
    return True
```

### IPT Torrent Metadata Parser
**File**: `services/api/app/utils/torrent_parser.py` (NEW)

Created comprehensive regex-based torrent title parser with 17+ metadata fields:
- **Video**: Resolution (2160p/1080p/720p), codec (HEVC/H.264), bit depth (10-bit)
- **Dolby Vision**: Profile detection (P5/P7/P8), FEL detection (P7 = BL+EL)
- **HDR**: HDR type (DV, HDR10, HDR10+, DV/HDR10)
- **Audio**: Codec (TrueHD/DTS-HD MA/Atmos), channels (5.1/7.1), Atmos detection
- **Release**: Source (BluRay/REMUX/WEB), type (EXTENDED/INTERNAL), group name
- **Metadata**: Clean title extraction, year, languages

**Quality Scoring System**:
- FEL (P7): 100 points
- DV P8: 90 points
- DV (any): 80 points
- 4K/2160p: 50 points
- Atmos: 20 points
- REMUX: 15 points, BluRay: 10 points
- TrueHD: 10 points, DTS-HD MA: 8 points

**Title Extraction Logic**:
1. First try: Extract title before year (for movies)
2. Second try: Extract before UHD/4K/2160p markers (for TV shows without years)
3. Third try: Extract before BluRay/REMUX/WEB markers (fallback)

Example parsing:
```
Input:  "End Of Watch 2012 2160p UHD BluRay DV P7 HDR REMUX DTS-HD MA 5.1 H265-BEN THE MEN"
Output: {
  clean_title: "End Of Watch",
  year: 2012,
  resolution: "2160p",
  dv_profile: "P7",
  has_fel: true,
  has_atmos: false,
  audio_codec: "DTS-HD MA",
  audio_channels: "5.1",
  video_codec: "HEVC",
  release_type: "REMUX",
  release_group: "BEN THE MEN",
  quality_score: 175
}
```

### IPT Service Enrichment
**File**: `services/api/app/services/ipt_service.py`

Integrated parser into IPT service to automatically enrich all torrent results:
- `_enrich_torrent()` method adds `metadata` field to each torrent
- Torrents sorted by quality score (highest first)
- FEL releases appear at top, followed by other DV profiles

### Frontend IPT Scanner Updates
**File**: `services/frontend/src/views/IPTScanner.vue`

Simplified IPT scanner table to remove redundant columns:
- **Removed**: Quality (2160p) column - all results are 4K from search query
- **Removed**: DV Profile column - all results are P7 FEL from `BL+EL+RPU` search
- **Kept**: Title, Year, Atmos, Audio, Size, Group, Link
- Filters reduced from 3 to 2 columns (Search + Show New Only)

**Rationale**: IPT scraper searches specifically for `BL+EL+RPU` (P7 FEL 4K), so showing those fields is redundant.

### IPT Scraper Pagination Support
**File**: `services/ipt-scraper/src/scraper.js`

Added multi-page scanning capability controlled by `SCAN_PAGES` environment variable:
- Defaults to 1 page (~100 torrents)
- Set `SCAN_PAGES=3` for 3 pages (~300 torrents) in docker-compose.yml
- Includes 2-second delay between pages to avoid rate limiting
- Deduplicates torrents by ID across pages

**Known Issue**: Pagination implementation complete but may need URL format adjustment (`&p=0` vs `&p=1`).

### Cache Management
**How it works**:
- Each scan fetches ~100 P7 FEL torrents from IPTorrents first page
- New torrents automatically added to "known torrents" cache
- Cache stores up to **1,000 torrents** (line 257: `slice(-1000)`)
- Older torrents trimmed when limit reached
- Cache persists in `/data/known_torrents.json` on scraper service

**Growth pattern**:
- First scan: 100 torrents cached
- Second scan: ~20 new torrents added → 120 total
- Continues until 1,000 limit reached
- No manual seeding required - grows organically

### Type Definitions
**File**: `services/frontend/src/api/types.ts`

Added `TorrentMetadata` interface with all parsed fields:
- Ensures type safety for metadata throughout frontend
- Matches backend parser output structure

**File**: `services/frontend/src/api/ipt.ts`

Updated API client to preserve `metadata` field from backend:
- Previously stripped during transformation
- Now passes through enriched metadata for display

# FELScanner v2 Deployment Guide

Complete deployment guide for FELScanner v2 in production environments.

## Quick Start

### Prerequisites

- Docker 24.0+ and Docker Compose 2.20+
- PostgreSQL 15+ (or use Docker Compose)
- Redis 7+ (or use Docker Compose)
- Plex Media Server (running and accessible)
- qBittorrent with Web UI enabled
- Radarr (optional, for folder path resolution)
- Telegram Bot (optional, for notifications)
- IPTorrents account (optional, for torrent scanning)

### Production Deployment

1. **Clone the repository:**

```bash
git clone https://github.com/yourusername/felscanner-v2.git
cd felscanner-v2
```

2. **Create production environment file:**

```bash
cp .env.production.example .env.production
```

3. **Edit `.env.production` with your configuration:**

Required variables:
- `POSTGRES_PASSWORD` - Strong database password
- `REDIS_PASSWORD` - Strong Redis password
- `PLEX_URL` - Your Plex server URL
- `PLEX_TOKEN` - Your Plex authentication token
- `QBITTORRENT_URL`, `QBITTORRENT_USERNAME`, `QBITTORRENT_PASSWORD`
- `RADARR_URL`, `RADARR_API_KEY`

Optional variables:
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` - For notifications
- `IPT_UID`, `IPT_PASS` - For IPTorrents scanning

4. **Start all services:**

```bash
docker-compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
```

5. **Verify services are running:**

```bash
docker-compose -f docker/docker-compose.prod.yml ps
```

All services should show "Up" status with healthy checks.

6. **Access the application:**

- Frontend: http://localhost:5173
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Migration from v1

If you're migrating from FELScanner v1:

1. **Backup your v1 database:**

```bash
cp /path/to/felscanner-v1/felscanner.db /path/to/backup/felscanner.db.backup
```

2. **Ensure v2 PostgreSQL is running:**

```bash
docker-compose -f docker/docker-compose.prod.yml up -d postgres
```

3. **Run migration script:**

```bash
pip install -r scripts/requirements.txt

python scripts/migrate_sqlite_to_postgres.py \
  --sqlite-db /path/to/felscanner-v1/felscanner.db \
  --postgres-url "postgresql://felscanner:YOUR_PASSWORD@localhost:5432/felscanner"
```

4. **Verify migration:**

The script will show migration statistics and verify row counts match.

5. **Start remaining services:**

```bash
docker-compose -f docker/docker-compose.prod.yml up -d
```

## Architecture

```
┌─────────────────┐
│   Nginx/Proxy   │ (Optional reverse proxy)
└────────┬────────┘
         │
    ┌────┴────┐
    │ Frontend│ (Vue 3 + Nginx)
    └────┬────┘
         │
    ┌────┴────┐
    │   API   │ (FastAPI)
    └────┬────┘
         │
    ┌────┴─────────┬──────────┐
    │              │          │
┌───┴────┐   ┌────┴───┐  ┌──┴────────┐
│ Redis  │   │Postgres│  │IPT Scraper│
└────────┘   └────────┘  └───────────┘
                             │
                         ┌───┴──────┐
                         │FlareSolverr│
                         └──────────┘
```

## Service Details

### Frontend (Port 5173)
- Vue 3 SPA served by Nginx
- Auto-refresh every 15 seconds
- Proxies `/api` requests to backend

### API (Port 8000)
- FastAPI with async SQLAlchemy
- Background tasks via APScheduler
- Prometheus metrics at `/metrics`
- Health check at `/health`
- OpenAPI docs at `/docs`

### IPT Scraper (Port 3000)
- Node.js + Express microservice
- Puppeteer for web scraping
- FlareSolverr for Cloudflare bypass
- Health check at `/health`

### PostgreSQL (Port 5432)
- Primary data store
- JSONB fields for flexible metadata
- Automatic backups recommended

### Redis (Port 6379)
- Task queue for background jobs
- Session storage
- Cache layer

### FlareSolverr (Port 8191)
- Cloudflare bypass service
- Used by IPT scraper
- Headless browser automation

## Configuration

### Auto-start Modes

Set `AUTO_START_MODE` in `.env.production`:

- `disabled` - Manual scan trigger only
- `scan` - Full library scan on startup
- `monitor` - Start monitor mode on startup (checks for new DV additions every minute)

### Scheduled Scans

Configure in application settings or environment:

- `SCAN_SCHEDULE_ENABLED=true`
- `SCAN_SCHEDULE_HOURS=0,12` - Run at midnight and noon

### Notification Rules

All 17 notification rules from v1 are preserved. Configure in application settings UI or environment variables:

- `NOTIFY_FEL=true` - Any FEL
- `NOTIFY_FEL_FROM_P5=true` - FEL upgrades from P5
- `NOTIFY_FEL_FROM_HDR=true` - FEL upgrades from HDR
- `NOTIFY_DV_ANY=true` - Any Dolby Vision
- `NOTIFY_ATMOS_ANY=true` - Any Atmos
- And 12 more...

## Monitoring

### Health Checks

All services expose health check endpoints:

```bash
# Frontend
curl http://localhost:5173/health

# API
curl http://localhost:8000/health

# IPT Scraper
curl http://localhost:3000/health
```

### Prometheus Metrics

API exposes Prometheus metrics at `/metrics`:

```bash
curl http://localhost:8000/metrics
```

Key metrics:
- `felscanner_scan_requests_total` - Total scan requests
- `felscanner_scan_duration_seconds` - Scan duration histogram
- `felscanner_active_downloads` - Active download count
- `felscanner_movies_total{category="dv"}` - Movie counts by category

### Logs

View logs for all services:

```bash
# All services
docker-compose -f docker/docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker/docker-compose.prod.yml logs -f api
```

Logs are structured JSON for easy parsing:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "app.services.scan",
  "message": "Scan completed",
  "context": {
    "movies_scanned": 487,
    "duration_seconds": 142
  }
}
```

## Backup & Recovery

### Database Backup

```bash
# Backup PostgreSQL
docker exec felscanner-postgres pg_dump -U felscanner felscanner > backup_$(date +%Y%m%d).sql

# Restore PostgreSQL
docker exec -i felscanner-postgres psql -U felscanner felscanner < backup_20240115.sql
```

### Volume Backup

```bash
# Backup all Docker volumes
docker run --rm \
  -v felscanner_postgres_data:/data/postgres \
  -v felscanner_redis_data:/data/redis \
  -v felscanner_ipt_data:/data/ipt \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/volumes_$(date +%Y%m%d).tar.gz /data
```

## Scaling

### Horizontal Scaling (Multiple API Instances)

1. Update `docker-compose.prod.yml`:

```yaml
api:
  deploy:
    replicas: 3
```

2. Add load balancer (e.g., Nginx):

```nginx
upstream api_backend {
    server api-1:8000;
    server api-2:8000;
    server api-3:8000;
}
```

### Vertical Scaling (Resource Limits)

```yaml
api:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 2G
      reservations:
        cpus: '1.0'
        memory: 1G
```

## Security

### Best Practices

1. **Change default passwords** in `.env.production`
2. **Use reverse proxy** (Nginx/Traefik) with SSL/TLS
3. **Firewall rules** - Only expose necessary ports
4. **Regular updates** - Keep Docker images updated
5. **Backup encryption** - Encrypt database backups
6. **Network isolation** - Use Docker networks

### SSL/TLS with Nginx

Example Nginx reverse proxy config:

```nginx
server {
    listen 443 ssl http2;
    server_name felscanner.yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://localhost:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Troubleshooting

### Service won't start

```bash
# Check logs
docker-compose -f docker/docker-compose.prod.yml logs api

# Common issues:
# - Missing required environment variables
# - Database not ready (wait for health check)
# - Port conflicts (check if ports are already in use)
```

### Database connection errors

```bash
# Test PostgreSQL connection
docker exec -it felscanner-postgres psql -U felscanner -d felscanner

# Check if database is initialized
docker exec felscanner-postgres psql -U felscanner -d felscanner -c "\dt"
```

### Scan not working

1. Check Plex connectivity from API container:
```bash
docker exec felscanner-api curl -I http://your-plex:32400
```

2. Verify Plex token is correct
3. Check API logs for detailed error messages

### IPT scraper failing

1. Verify FlareSolverr is running:
```bash
curl http://localhost:8191/health
```

2. Check IPT credentials
3. Review IPT scraper logs for Cloudflare errors

## Performance Tuning

### PostgreSQL

Edit `postgresql.conf` for production:

```ini
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB
maintenance_work_mem = 128MB
max_connections = 100
```

### API Workers

Adjust Uvicorn workers in `Dockerfile`:

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

Rule of thumb: `workers = (2 × CPU cores) + 1`

## Support

For issues, questions, or contributions:

- GitHub Issues: https://github.com/yourusername/felscanner-v2/issues
- Documentation: https://github.com/yourusername/felscanner-v2/wiki
- Discord: [Your Discord Server]

## License

[Your License Here]

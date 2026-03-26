"""
Prometheus metrics for FELScanner API

Exposes custom application metrics for monitoring via Prometheus/Grafana.
"""

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from typing import Callable
import time


# ============================================================================
# Scan Metrics
# ============================================================================

scan_requests_total = Counter(
    'felscanner_scan_requests_total',
    'Total number of scan requests',
    ['scan_type']  # full, verify, monitor
)

scan_duration_seconds = Histogram(
    'felscanner_scan_duration_seconds',
    'Duration of scan operations in seconds',
    ['scan_type'],
    buckets=[10, 30, 60, 120, 300, 600, 1200, 1800]  # 10s to 30min
)

scan_errors_total = Counter(
    'felscanner_scan_errors_total',
    'Total number of scan errors',
    ['error_type']
)

movies_scanned_total = Counter(
    'felscanner_movies_scanned_total',
    'Total number of movies scanned'
)

# ============================================================================
# Movie Metrics
# ============================================================================

movies_total = Gauge(
    'felscanner_movies_total',
    'Total number of movies in library',
    ['category']  # all, dv, dv_p7, dv_p5, dv_fel, atmos, 4k, 1080p
)

# ============================================================================
# Download Metrics
# ============================================================================

pending_downloads = Gauge(
    'felscanner_pending_downloads',
    'Number of pending download approvals'
)

active_torrents = Gauge(
    'felscanner_active_torrents',
    'Number of active torrents',
    ['state']  # downloading, seeding, paused
)

download_approvals_total = Counter(
    'felscanner_download_approvals_total',
    'Total number of download approvals',
    ['action']  # approved, declined, expired
)

# ============================================================================
# Connection Metrics
# ============================================================================

connection_status = Gauge(
    'felscanner_connection_status',
    'Service connection status (1=connected, 0=disconnected)',
    ['service']  # plex, qbittorrent, radarr, telegram, flaresolverr, ipt_scraper
)

connection_check_duration_seconds = Histogram(
    'felscanner_connection_check_duration_seconds',
    'Duration of connection checks in seconds',
    ['service'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# ============================================================================
# API Metrics
# ============================================================================

http_requests_total = Counter(
    'felscanner_http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status_code']
)

http_request_duration_seconds = Histogram(
    'felscanner_http_request_duration_seconds',
    'Duration of HTTP requests in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# ============================================================================
# Background Task Metrics
# ============================================================================

background_tasks_total = Counter(
    'felscanner_background_tasks_total',
    'Total number of background tasks executed',
    ['task_name', 'status']  # success, failure
)

background_task_duration_seconds = Histogram(
    'felscanner_background_task_duration_seconds',
    'Duration of background tasks in seconds',
    ['task_name'],
    buckets=[1, 5, 10, 30, 60, 300, 600]
)

# ============================================================================
# Database Metrics
# ============================================================================

database_query_duration_seconds = Histogram(
    'felscanner_database_query_duration_seconds',
    'Duration of database queries in seconds',
    ['operation'],  # select, insert, update, delete
    buckets=[0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

database_connections = Gauge(
    'felscanner_database_connections',
    'Number of database connections',
    ['state']  # active, idle
)

# ============================================================================
# Utility Functions
# ============================================================================

def record_scan_metrics(scan_type: str, duration: float, movies_count: int, success: bool = True):
    """Record metrics for a scan operation"""
    scan_requests_total.labels(scan_type=scan_type).inc()
    scan_duration_seconds.labels(scan_type=scan_type).observe(duration)
    movies_scanned_total.inc(movies_count)

    if not success:
        scan_errors_total.labels(error_type=scan_type).inc()


def record_movie_statistics(stats: dict):
    """Update movie statistics gauges"""
    movies_total.labels(category='all').set(stats.get('total', 0))
    movies_total.labels(category='dv').set(stats.get('dv_total', 0))
    movies_total.labels(category='dv_p7').set(stats.get('dv_p7', 0))
    movies_total.labels(category='dv_p5').set(stats.get('dv_p5', 0))
    movies_total.labels(category='dv_fel').set(stats.get('dv_fel', 0))
    movies_total.labels(category='atmos').set(stats.get('atmos_total', 0))
    movies_total.labels(category='4k').set(stats.get('resolution_4k', 0))
    movies_total.labels(category='1080p').set(stats.get('resolution_1080p', 0))


def record_download_metrics(pending: int, active_by_state: dict):
    """Update download metrics"""
    pending_downloads.set(pending)

    for state, count in active_by_state.items():
        active_torrents.labels(state=state).set(count)


def record_connection_status(service: str, connected: bool, check_duration: float):
    """Record connection status and check duration"""
    connection_status.labels(service=service).set(1 if connected else 0)
    connection_check_duration_seconds.labels(service=service).observe(check_duration)


def record_http_request(method: str, endpoint: str, status_code: int, duration: float):
    """Record HTTP request metrics"""
    http_requests_total.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)


def record_background_task(task_name: str, duration: float, success: bool = True):
    """Record background task metrics"""
    status = 'success' if success else 'failure'
    background_tasks_total.labels(task_name=task_name, status=status).inc()
    background_task_duration_seconds.labels(task_name=task_name).observe(duration)


class PrometheusMiddleware:
    """FastAPI middleware to record HTTP request metrics"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Skip metrics endpoint to avoid recursion
        if scope["path"] == "/metrics":
            return await self.app(scope, receive, send)

        method = scope["method"]
        path = scope["path"]

        # Simplify path for metrics (remove IDs, etc.)
        endpoint = self._simplify_path(path)

        start_time = time.time()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                duration = time.time() - start_time
                status_code = message["status"]
                record_http_request(method, endpoint, status_code, duration)

            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _simplify_path(self, path: str) -> str:
        """Simplify path for metrics (replace IDs with placeholders)"""
        parts = path.split('/')

        # Replace numeric IDs with {id}
        simplified = []
        for part in parts:
            if part.isdigit():
                simplified.append('{id}')
            else:
                simplified.append(part)

        return '/'.join(simplified)


def metrics_endpoint() -> Response:
    """Endpoint handler for /metrics"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

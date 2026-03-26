"""
Connections API Endpoints
External service health monitoring
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.integrations.plex.client import PlexClient
from app.models.connection_status import ConnectionStatus

router = APIRouter()
logger = get_logger(__name__)


@router.get("/status", response_model=dict[str, Any])
async def get_all_connections_status(db: AsyncSession = Depends(get_db)):
    """
    Get status of all external service connections

    Returns current health status for:
    - Plex
    - qBittorrent
    - Radarr
    - Telegram
    - IPT Scraper
    """
    result = await db.execute(select(ConnectionStatus))
    connections = result.scalars().all()

    status_dict = {}
    for conn in connections:
        status_dict[conn.service] = {
            "is_connected": conn.is_connected,
            "status_message": conn.status_message,
            "error_message": conn.error_message,
            "response_time_ms": conn.response_time_ms,
            "last_checked_at": conn.last_checked_at,
            "last_success_at": conn.last_success_at,
            "last_failure_at": conn.last_failure_at,
            "consecutive_failures": conn.consecutive_failures,
            "uptime_percent": conn.uptime_percent,
            "version": conn.version,
        }

    return status_dict


@router.get("/{service}/status", response_model=dict[str, Any])
async def get_service_status(
    service: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get status of a specific service

    Services: plex, qbittorrent, radarr, telegram, ipt_scraper
    """
    result = await db.execute(
        select(ConnectionStatus).where(ConnectionStatus.service == service)
    )
    conn = result.scalar_one_or_none()

    if not conn:
        return {
            "service": service,
            "is_connected": False,
            "status_message": "No status recorded",
        }

    return {
        "service": conn.service,
        "is_connected": conn.is_connected,
        "status_message": conn.status_message,
        "error_message": conn.error_message,
        "response_time_ms": conn.response_time_ms,
        "last_checked_at": conn.last_checked_at,
        "last_success_at": conn.last_success_at,
        "last_failure_at": conn.last_failure_at,
        "consecutive_failures": conn.consecutive_failures,
        "total_checks": conn.total_checks,
        "total_failures": conn.total_failures,
        "uptime_percent": conn.uptime_percent,
        "version": conn.version,
        "extra_data": conn.extra_data,
    }


@router.post("/{service}/check", response_model=dict[str, Any])
async def check_service_connection(
    service: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger a connection check for a service

    Performs a health check and updates the connection status.
    """
    settings = get_settings()
    start_time = datetime.now()

    is_connected = False
    status_message = ""
    error_message = None
    version = None

    try:
        if service == "plex":
            client = PlexClient()
            is_connected = await client.connect()
            if is_connected:
                info = await client.get_server_info()
                status_message = f"Connected to {info['name']}"
                version = info.get("version")
            else:
                error_message = "Failed to connect to Plex server"

        elif service == "qbittorrent":
            # TODO: Implement qBittorrent health check
            status_message = "Health check not implemented"

        elif service == "radarr":
            # TODO: Implement Radarr health check
            status_message = "Health check not implemented"

        elif service == "telegram":
            # TODO: Implement Telegram health check
            status_message = "Health check not implemented"

        elif service == "ipt_scraper":
            # TODO: Implement IPT scraper health check
            status_message = "Health check not implemented"

        else:
            error_message = "Unknown service"

    except Exception as e:
        is_connected = False
        error_message = str(e)
        logger.error(f"connection.check_failed.{service}", error=str(e))

    # Calculate response time
    end_time = datetime.now()
    response_time_ms = int((end_time - start_time).total_seconds() * 1000)

    # Update or create connection status
    result = await db.execute(
        select(ConnectionStatus).where(ConnectionStatus.service == service)
    )
    conn = result.scalar_one_or_none()

    if conn:
        # Update existing
        conn.is_connected = is_connected
        conn.status_message = status_message
        conn.error_message = error_message
        conn.response_time_ms = response_time_ms
        conn.last_checked_at = end_time
        conn.total_checks += 1
        conn.version = version

        if is_connected:
            conn.consecutive_failures = 0
            conn.last_success_at = end_time
        else:
            conn.consecutive_failures += 1
            conn.total_failures += 1
            conn.last_failure_at = end_time

    else:
        # Create new
        conn = ConnectionStatus(
            service=service,
            is_connected=is_connected,
            status_message=status_message,
            error_message=error_message,
            response_time_ms=response_time_ms,
            last_checked_at=end_time,
            total_checks=1,
            total_failures=0 if is_connected else 1,
            consecutive_failures=0 if is_connected else 1,
            last_success_at=end_time if is_connected else None,
            last_failure_at=end_time if not is_connected else None,
            version=version,
        )
        db.add(conn)

    await db.commit()
    await db.refresh(conn)

    logger.info(
        f"connection.checked.{service}",
        is_connected=is_connected,
        response_time_ms=response_time_ms,
    )

    return {
        "service": service,
        "is_connected": is_connected,
        "status_message": status_message,
        "error_message": error_message,
        "response_time_ms": response_time_ms,
        "checked_at": end_time,
    }


@router.post("/check-all", response_model=dict[str, Any])
async def check_all_connections(db: AsyncSession = Depends(get_db)):
    """
    Check all configured service connections

    Triggers health checks for all enabled services.
    """
    settings = get_settings()
    results = {}

    # Check Plex (always required)
    results["plex"] = await check_service_connection("plex", db)

    # Check optional services if configured
    if settings.QBITTORRENT_HOST:
        results["qbittorrent"] = await check_service_connection("qbittorrent", db)

    if settings.RADARR_URL:
        results["radarr"] = await check_service_connection("radarr", db)

    if settings.TELEGRAM_ENABLED:
        results["telegram"] = await check_service_connection("telegram", db)

    # Always check IPT scraper
    results["ipt_scraper"] = await check_service_connection("ipt_scraper", db)

    all_connected = all(r["is_connected"] for r in results.values())

    return {
        "all_connected": all_connected,
        "services": results,
    }

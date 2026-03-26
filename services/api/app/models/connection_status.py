"""
ConnectionStatus ORM Model
Tracks health status of external service integrations
"""
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConnectionStatus(Base):
    """
    External service connection health

    Stores status of all integrations (Plex, qBittorrent, Radarr, etc.)
    for health monitoring and dashboard display.
    """

    __tablename__ = "connection_status"

    # Primary Key (service name)
    service: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        comment="Service identifier (plex, qbittorrent, radarr, telegram, ipt_scraper)",
    )

    # Status
    is_connected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metrics
    response_time_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Last check response time"
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_checks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Service Metadata
    version: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Service version if available"
    )
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Service-specific metadata (Plex library count, qBit torrents, etc.)",
    )

    # Timestamps
    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        return f"<ConnectionStatus(service='{self.service}', status={status})>"

    @property
    def uptime_percent(self) -> float:
        """Calculate uptime percentage"""
        if self.total_checks == 0:
            return 0.0
        successes = self.total_checks - self.total_failures
        return (successes / self.total_checks) * 100

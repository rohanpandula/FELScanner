"""
ScanHistory ORM Model
Audit trail for library scan operations
"""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScanHistory(Base):
    """
    Scan operation history

    Tracks all library scans with performance metrics,
    discovery counts, and error logging.
    """

    __tablename__ = "scan_history"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Scan Metadata
    scan_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="full, verify, monitor, ipt_check",
    )
    trigger: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="manual, scheduled, auto_monitor, webhook",
    )
    triggered_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="User or system that initiated"
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="running",
        index=True,
        comment="running, completed, failed, cancelled",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Results
    movies_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    movies_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    movies_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    movies_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Discovery Counts
    dv_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fel_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    atmos_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Performance Metrics
    duration_seconds: Mapped[float | None] = mapped_column(
        Integer, nullable=True, comment="Scan duration in seconds"
    )
    plex_api_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ffprobe_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Collection Updates
    collections_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Additional Data
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed progress log, errors, etc.",
    )

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<ScanHistory(id={self.id}, scan_type={self.scan_type}, "
            f"status={self.status}, movies_scanned={self.movies_scanned})>"
        )

    @property
    def is_running(self) -> bool:
        """Check if scan is currently running"""
        return self.status == "running"

    @property
    def is_completed(self) -> bool:
        """Check if scan completed successfully"""
        return self.status == "completed"

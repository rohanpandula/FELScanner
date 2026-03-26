"""
DownloadHistory ORM Model
Audit trail for all download requests and outcomes
"""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DownloadHistory(Base):
    """
    Download history audit trail

    Records all download requests (approved, declined, expired)
    for reporting and analytics.
    """

    __tablename__ = "download_history"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Torrent Information
    torrent_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    torrent_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Movie Information
    movie_title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    movie_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    movie_rating_key: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Outcome
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="approved, declined, expired, failed",
    )
    action_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Username who took action"
    )
    action_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Quality Information
    quality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    upgrade_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Integration Status
    qbittorrent_hash: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="qBittorrent torrent hash if added"
    )
    radarr_download_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Radarr download ID if sent"
    )
    download_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    download_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Metadata
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Full torrent metadata, download stats, etc.",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<DownloadHistory(id={self.id}, torrent_id='{self.torrent_id}', "
            f"action={self.action}, movie='{self.movie_title}')>"
        )

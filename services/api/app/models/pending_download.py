"""
PendingDownload ORM Model
Represents download approval requests awaiting user action
"""
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PendingDownload(Base):
    """
    Download approval request

    Represents a torrent waiting for user approval via Telegram.
    Includes upgrade detection metadata and expiration logic.
    """

    __tablename__ = "pending_downloads"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Torrent Identification
    torrent_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="IPTorrents torrent ID",
    )
    torrent_name: Mapped[str] = mapped_column(String(500), nullable=False)
    torrent_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Movie Association
    movie_title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    movie_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    movie_rating_key: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Plex rating_key if matched"
    )

    # Quality Information
    quality: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Parsed quality string"
    )
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dv_profile: Mapped[str | None] = mapped_column(String(10), nullable=True)
    has_fel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_atmos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Upgrade Detection
    upgrade_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="e.g., P5->P7, HDR->DV, resolution, atmos",
    )
    is_upgrade: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    is_duplicate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Already have this quality"
    )

    # Torrent Metadata
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seeders: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leechers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Approval Workflow
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending, approved, declined, expired",
    )
    telegram_message_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Telegram message for inline buttons"
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Telegram username who approved"
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    declined_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Expiration
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Auto-decline after this time",
    )

    # Additional Data
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Current movie versions, notification rule matched, etc.",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<PendingDownload(id={self.id}, torrent_id='{self.torrent_id}', "
            f"movie='{self.movie_title}', status={self.status})>"
        )

    @property
    def is_expired(self) -> bool:
        """Check if download request has expired"""
        return datetime.now(self.expires_at.tzinfo) > self.expires_at

    @property
    def is_pending(self) -> bool:
        """Check if download is still awaiting approval"""
        return self.status == "pending" and not self.is_expired

    @property
    def display_quality(self) -> str:
        """Human-readable quality string"""
        parts = []

        if self.resolution:
            parts.append(self.resolution)

        if self.has_fel:
            parts.append("DV P7 FEL")
        elif self.dv_profile:
            parts.append(f"DV {self.dv_profile}")

        if self.has_atmos:
            parts.append("Atmos")

        return " / ".join(parts) if parts else self.quality or "Unknown"

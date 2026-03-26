"""
MetadataCache ORM Model
Stores ffprobe metadata (replaces metadata-cache.json)
"""
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MetadataCache(Base):
    """
    FFProbe metadata cache

    Stores detailed video/audio stream information from ffprobe.
    Replaces metadata-cache.json with database storage.
    """

    __tablename__ = "metadata_cache"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Movie Association
    rating_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Plex rating_key",
    )

    # File Information
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # FFProbe Data
    ffprobe_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Complete ffprobe JSON output",
    )

    # Parsed Streams
    video_streams: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Parsed video stream metadata",
    )
    audio_streams: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Parsed audio stream metadata",
    )
    subtitle_streams: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Subtitle stream metadata",
    )

    # Cache Management
    is_stale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Needs refresh"
    )
    ttl_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=86400,
        comment="Time to live (24 hours default)",
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
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Auto-refresh after this time",
    )

    def __repr__(self) -> str:
        return f"<MetadataCache(rating_key='{self.rating_key}', file_path='{self.file_path}')>"

    @property
    def is_expired(self) -> bool:
        """Check if cache has expired"""
        return datetime.now(self.expires_at.tzinfo) > self.expires_at

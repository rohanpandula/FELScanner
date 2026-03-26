"""
Movie ORM Model
Core entity representing movies in the Plex library
"""
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Movie(Base):
    """
    Movie entity with Dolby Vision metadata

    Stores comprehensive movie information including:
    - Plex metadata (rating_key, title, year)
    - Video quality (resolution, codecs, HDR type)
    - Dolby Vision profile and FEL detection
    - Audio metadata (TrueHD Atmos detection)
    - File paths and versions
    """

    __tablename__ = "movies"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Plex Identifiers
    rating_key: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Plex unique identifier",
    )

    # Basic Metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_title: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Video Quality
    resolution: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True, comment="e.g., 2160p, 1080p"
    )
    video_codec: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="e.g., hevc, h264"
    )
    hdr_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True, comment="e.g., dolbyvision, hdr10, sdr"
    )

    # Dolby Vision
    dv_profile: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        index=True,
        comment="Dolby Vision profile (P4, P5, P7, P8, P9)",
    )
    dv_fel: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Has FEL (Profile 7)",
    )
    dv_bl_compatible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Base layer is HDR10 compatible",
    )

    # Audio
    audio_codec: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Primary audio codec"
    )
    has_atmos: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Has TrueHD Atmos track",
    )
    audio_channels: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="e.g., 7.1, 5.1"
    )

    # File Information
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    container: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="e.g., mkv, mp4"
    )

    # Plex Collections
    in_dv_collection: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    in_p7_collection: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    in_atmos_collection: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    # Version Management
    version_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Number of versions in Plex"
    )
    best_version_index: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Index of best quality version"
    )

    # Extended Metadata (JSONB)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata (versions, streams, quality scores)",
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
    last_scanned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<Movie(id={self.id}, title='{self.title}', year={self.year}, "
            f"dv_profile={self.dv_profile}, dv_fel={self.dv_fel})>"
        )

    @property
    def is_dolby_vision(self) -> bool:
        """Check if movie has any Dolby Vision profile"""
        return self.dv_profile is not None and self.dv_profile.startswith("P")

    @property
    def is_fel(self) -> bool:
        """Check if movie has FEL (Profile 7)"""
        return self.dv_fel is True

    @property
    def is_4k(self) -> bool:
        """Check if movie is 4K resolution"""
        return self.resolution in ("2160p", "4K")

    @property
    def quality_score(self) -> int:
        """
        Calculate quality score for version ranking.

        Delegates to the consolidated quality scoring module.
        """
        from app.utils.quality_scoring import calculate_library_quality_score

        return calculate_library_quality_score({
            "dv_fel": self.dv_fel,
            "dv_profile": self.dv_profile,
            "resolution": self.resolution,
            "has_atmos": self.has_atmos,
        })

    @property
    def display_quality(self) -> str:
        """Human-readable quality string"""
        parts = []

        if self.resolution:
            parts.append(self.resolution)

        if self.is_fel:
            parts.append("DV P7 FEL")
        elif self.dv_profile:
            parts.append(f"DV {self.dv_profile}")
        elif self.hdr_type and self.hdr_type.lower() != "sdr":
            parts.append(self.hdr_type.upper())

        if self.has_atmos:
            parts.append("Atmos")

        return " / ".join(parts) if parts else "Unknown"

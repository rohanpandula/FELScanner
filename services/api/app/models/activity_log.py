"""
ActivityLog ORM Model
Chronological feed of all significant events
"""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ActivityLog(Base):
    """
    Activity feed event.

    Captures all significant events: movie additions, upgrades,
    downloads, scans, collection changes, etc.
    """

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="movie_added, movie_upgraded, download_approved, scan_completed, etc.",
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    severity: Mapped[str] = mapped_column(
        String(20), default="info", comment="info, success, warning, error"
    )

    # Movie association (optional)
    movie_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("movies.id", ondelete="SET NULL"), nullable=True
    )
    movie_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    movie_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Generic relation to other entities
    related_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    related_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Quality change tracking (for upgrade events)
    quality_before: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quality_after: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Extra data
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, name="metadata"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<ActivityLog(id={self.id}, type='{self.event_type}', "
            f"title='{self.title[:50]}')>"
        )

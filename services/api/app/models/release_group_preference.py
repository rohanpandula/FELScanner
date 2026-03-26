"""
ReleaseGroupPreference ORM Model
Tracks release group reputation and user preferences
"""
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReleaseGroupPreference(Base):
    """
    Release group preferences and aggregated statistics.

    Tracks user preferences (preferred/blocked) and automatically
    aggregated stats from IPT scan results and download history.
    """

    __tablename__ = "release_group_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    group_name: Mapped[str] = mapped_column(
        String(200), unique=True, nullable=False, index=True
    )

    # User preferences
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # Aggregated stats
    avg_file_size_gb: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    total_releases_seen: Mapped[int] = mapped_column(Integer, default=0)
    total_downloads: Mapped[int] = mapped_column(Integer, default=0)
    avg_quality_score: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Extra
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, name="metadata"
    )

    def __repr__(self) -> str:
        return (
            f"<ReleaseGroupPreference(group='{self.group_name}', "
            f"preferred={self.is_preferred}, seen={self.total_releases_seen})>"
        )

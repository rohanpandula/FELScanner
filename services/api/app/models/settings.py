"""
Setting ORM Model
Key-value store for application settings (replaces settings.json)
"""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Setting(Base):
    """
    Application settings key-value store

    Replaces settings.json with database-backed configuration.
    Supports both simple values and complex JSON structures.
    """

    __tablename__ = "settings"

    # Primary Key (setting key)
    key: Mapped[str] = mapped_column(
        String(100), primary_key=True, comment="Setting identifier"
    )

    # Value Storage
    value: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Setting value (supports complex structures)",
    )
    value_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Alternative text storage for large values"
    )

    # Metadata
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Human-readable description"
    )
    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="e.g., notifications, collections, integrations",
    )

    # Versioning
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Setting schema version"
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
    updated_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="User who last updated"
    )

    def __repr__(self) -> str:
        return f"<Setting(key='{self.key}', category={self.category})>"

"""
CollectionChange ORM Model
Audit trail for Plex collection modifications
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CollectionChange(Base):
    """
    Collection modification audit trail

    Tracks all additions/removals from Plex collections
    (All DV, DV P7 FEL, TrueHD Atmos).
    """

    __tablename__ = "collection_changes"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Collection Information
    collection_name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    collection_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="dv_all, dv_p7, atmos",
    )

    # Movie Information
    movie_rating_key: Mapped[str] = mapped_column(String(50), nullable=False)
    movie_title: Mapped[str] = mapped_column(String(500), nullable=False)
    movie_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Change Type
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="added, removed",
    )
    reason: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Why the change was made"
    )

    # Trigger
    triggered_by: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="scan, manual, auto_verify",
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
            f"<CollectionChange(id={self.id}, collection='{self.collection_name}', "
            f"action={self.action}, movie='{self.movie_title}')>"
        )

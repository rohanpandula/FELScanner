"""
NotificationQueue ORM Model
Persistent queue for Telegram notifications
"""
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NotificationQueue(Base):
    """
    Notification queue for reliable delivery

    Ensures Telegram notifications are delivered even if
    the service is temporarily unavailable.
    """

    __tablename__ = "notification_queue"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Notification Type
    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="download_approval, upgrade_found, scan_complete, error",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        index=True,
        comment="1=highest, 10=lowest",
    )

    # Content
    message: Mapped[str] = mapped_column(Text, nullable=False)
    parse_mode: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="HTML, Markdown, MarkdownV2"
    )

    # Telegram-specific
    reply_markup: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="InlineKeyboard JSON for approval buttons",
    )
    disable_notification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending, sent, failed, cancelled",
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Telegram Response
    telegram_message_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Telegram message ID after sending"
    )

    # Additional Data
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Related download ID, movie rating_key, etc.",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="When to send (for delayed notifications)",
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationQueue(id={self.id}, type='{self.notification_type}', "
            f"status={self.status}, attempts={self.attempts})>"
        )

    @property
    def can_retry(self) -> bool:
        """Check if notification can be retried"""
        return self.status == "failed" and self.attempts < self.max_attempts

    @property
    def is_pending(self) -> bool:
        """Check if notification is ready to send"""
        return (
            self.status == "pending"
            and datetime.now(self.scheduled_at.tzinfo) >= self.scheduled_at
        )

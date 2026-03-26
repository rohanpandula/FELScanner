"""
Telegram Notifier
Formats and sends notifications via Telegram
"""
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.telegram.handler import TelegramHandler
from app.models.notification_queue import NotificationQueue

logger = get_logger(__name__)


class TelegramNotifier:
    """
    Telegram notification service

    Formats messages and manages notification queue.
    """

    def __init__(self, db: AsyncSession):
        """Initialize notifier"""
        self.db = db
        self.settings = get_settings()
        self.handler = TelegramHandler()

    def format_approval_message(
        self,
        movie_title: str,
        movie_year: int | None,
        torrent_name: str,
        quality: str,
        upgrade_type: str | None,
        size_mb: float | None,
        seeders: int | None,
    ) -> str:
        """
        Format download approval request message

        Args:
            movie_title: Movie title
            movie_year: Release year
            torrent_name: Torrent name
            quality: Quality string
            upgrade_type: Type of upgrade
            size_mb: File size in MB
            seeders: Number of seeders

        Returns:
            str: Formatted HTML message
        """
        year_str = f" ({movie_year})" if movie_year else ""

        message = f"<b>🎬 New Download Available</b>\n\n"
        message += f"<b>Movie:</b> {movie_title}{year_str}\n"
        message += f"<b>Quality:</b> {quality}\n"

        if upgrade_type:
            message += f"<b>Upgrade:</b> {upgrade_type}\n"

        if size_mb:
            message += f"<b>Size:</b> {size_mb:.1f} MB\n"

        if seeders:
            message += f"<b>Seeders:</b> {seeders}\n"

        message += f"\n<code>{torrent_name}</code>\n"
        message += f"\n<i>Expires in {self.settings.NOTIFY_EXPIRE_HOURS} hours</i>"

        return message

    def format_scan_complete_message(
        self,
        movies_scanned: int,
        dv_discovered: int,
        fel_discovered: int,
        atmos_discovered: int,
        duration_seconds: float,
    ) -> str:
        """
        Format scan completion notification

        Args:
            movies_scanned: Number of movies scanned
            dv_discovered: DV movies found
            fel_discovered: FEL movies found
            atmos_discovered: Atmos movies found
            duration_seconds: Scan duration

        Returns:
            str: Formatted message
        """
        message = "<b>✅ Library Scan Complete</b>\n\n"
        message += f"<b>Movies Scanned:</b> {movies_scanned}\n"
        message += f"<b>Dolby Vision:</b> {dv_discovered}\n"
        message += f"<b>DV FEL (P7):</b> {fel_discovered}\n"
        message += f"<b>TrueHD Atmos:</b> {atmos_discovered}\n"
        message += f"<b>Duration:</b> {duration_seconds:.1f}s\n"

        return message

    def format_upgrade_found_message(
        self,
        movie_title: str,
        current_quality: str,
        new_quality: str,
        upgrade_type: str,
    ) -> str:
        """Format upgrade discovery notification"""
        message = "<b>⬆️ Upgrade Available</b>\n\n"
        message += f"<b>Movie:</b> {movie_title}\n"
        message += f"<b>Current:</b> {current_quality}\n"
        message += f"<b>New:</b> {new_quality}\n"
        message += f"<b>Type:</b> {upgrade_type}\n"

        return message

    async def queue_approval_notification(
        self,
        download_id: int,
        message: str,
        priority: int = 5,
    ) -> NotificationQueue:
        """
        Queue a download approval notification

        Args:
            download_id: Pending download ID
            message: Notification message
            priority: Priority (1=highest, 10=lowest)

        Returns:
            NotificationQueue: Queued notification
        """
        notification = NotificationQueue(
            notification_type="download_approval",
            priority=priority,
            message=message,
            parse_mode="HTML",
            reply_markup={
                "inline_keyboard": [
                    [
                        {"text": "✅ Approve", "callback_data": f"approve:{download_id}"},
                        {"text": "❌ Decline", "callback_data": f"decline:{download_id}"},
                    ]
                ]
            },
            extra_data={"download_id": download_id},
            scheduled_at=datetime.now(),
        )

        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        logger.info("notification.queued", id=notification.id, type="download_approval")

        return notification

    async def queue_simple_notification(
        self,
        notification_type: str,
        message: str,
        priority: int = 5,
        delay_seconds: int = 0,
    ) -> NotificationQueue:
        """
        Queue a simple notification

        Args:
            notification_type: Type of notification
            message: Message text
            priority: Priority level
            delay_seconds: Delay before sending

        Returns:
            NotificationQueue: Queued notification
        """
        scheduled_at = datetime.now() + timedelta(seconds=delay_seconds)

        notification = NotificationQueue(
            notification_type=notification_type,
            priority=priority,
            message=message,
            parse_mode="HTML",
            scheduled_at=scheduled_at,
        )

        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        logger.info("notification.queued", id=notification.id, type=notification_type)

        return notification

    async def process_pending_notifications(self) -> int:
        """
        Process all pending notifications in queue

        Returns:
            int: Number of notifications sent
        """
        if not self.settings.TELEGRAM_ENABLED:
            return 0

        # Get pending notifications
        result = await self.db.execute(
            select(NotificationQueue)
            .where(NotificationQueue.status == "pending")
            .where(NotificationQueue.scheduled_at <= datetime.now())
            .order_by(NotificationQueue.priority.asc(), NotificationQueue.created_at.asc())
            .limit(10)  # Process in batches
        )
        notifications = result.scalars().all()

        sent_count = 0

        for notification in notifications:
            try:
                # Initialize handler if needed
                if not self.handler._application:
                    await self.handler.initialize()

                # Send notification
                if notification.reply_markup:
                    # Approval request with buttons
                    download_id = notification.extra_data.get("download_id")
                    message_id = await self.handler.send_approval_request(
                        download_id=download_id,
                        message=notification.message,
                    )
                else:
                    # Simple notification
                    message_id = await self.handler.send_notification(
                        message=notification.message,
                        parse_mode=notification.parse_mode or "HTML",
                        disable_notification=notification.disable_notification,
                    )

                if message_id:
                    notification.status = "sent"
                    notification.sent_at = datetime.now()
                    notification.telegram_message_id = message_id
                    sent_count += 1
                    logger.info("notification.sent", id=notification.id)
                else:
                    notification.status = "failed"
                    notification.attempts += 1
                    notification.last_error = "Failed to send message"
                    logger.error("notification.send_failed", id=notification.id)

            except Exception as e:
                notification.status = "failed"
                notification.attempts += 1
                notification.last_error = str(e)
                logger.error("notification.send_error", id=notification.id, error=str(e))

            await self.db.commit()

        return sent_count

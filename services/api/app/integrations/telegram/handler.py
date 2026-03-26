"""
Telegram Handler
Manages inline keyboard interactions and webhook callbacks
"""
import hashlib
import hmac
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TelegramHandler:
    """
    Telegram bot handler for download approvals

    Manages inline keyboards for approve/decline buttons
    and processes webhook callbacks from Telegram.
    """

    def __init__(self):
        """Initialize Telegram handler"""
        self.settings = get_settings()
        self._application: Application | None = None

    async def initialize(self) -> bool:
        """
        Initialize Telegram bot application

        Returns:
            bool: True if initialized successfully
        """
        if not self.settings.TELEGRAM_ENABLED:
            logger.info("telegram.disabled")
            return False

        if not self.settings.TELEGRAM_TOKEN:
            logger.error("telegram.no_token")
            return False

        try:
            self._application = (
                Application.builder()
                .token(self.settings.TELEGRAM_TOKEN)
                .build()
            )

            # Register handlers
            self._application.add_handler(
                CallbackQueryHandler(self._handle_callback)
            )
            self._application.add_handler(
                CommandHandler("start", self._handle_start)
            )

            # Initialize bot
            await self._application.initialize()
            await self._application.start()

            logger.info("telegram.initialized")
            return True

        except Exception as e:
            logger.error("telegram.init_failed", error=str(e))
            return False

    async def shutdown(self):
        """Shutdown Telegram bot"""
        if self._application:
            await self._application.stop()
            await self._application.shutdown()
            logger.info("telegram.shutdown")

    async def _handle_start(self, update: Update, context: Any):
        """Handle /start command"""
        if update.message:
            await update.message.reply_text(
                "FELScanner v2 - Download approval bot initialized.\n"
                "You will receive notifications for upgrade opportunities."
            )

    async def _handle_callback(self, update: Update, context: Any):
        """
        Handle inline button callbacks.

        Processes download approval/decline via the shared download service.

        Callback data format: "action:download_id"
        - approve:123
        - decline:123
        """
        query = update.callback_query
        if not query:
            return

        await query.answer()

        # Parse callback data
        data = query.data
        if not data or ":" not in data:
            await query.edit_message_text("Invalid callback data")
            return

        action, download_id_str = data.split(":", 1)

        try:
            download_id = int(download_id_str)
        except ValueError:
            await query.edit_message_text("Invalid download ID")
            return

        username = query.from_user.username or str(query.from_user.id)

        # Process via shared download service
        from app.core.database import get_session_factory
        from app.services.download_service import DownloadActionError, process_download_action

        session_factory = get_session_factory()
        async with session_factory() as db:
            try:
                download = await process_download_action(
                    db=db,
                    download_id=download_id,
                    action=action,
                    actor=username,
                )

                if action == "approve":
                    await query.edit_message_text(
                        f"✅ Download approved!\n\n{query.message.text}\n\n"
                        f"Status: Approved by {username}"
                    )
                elif action == "decline":
                    await query.edit_message_text(
                        f"❌ Download declined.\n\n{query.message.text}\n\n"
                        f"Status: Declined by {username}"
                    )

            except DownloadActionError as e:
                await query.edit_message_text(
                    f"⚠️ Action failed: {e.message}\n\n{query.message.text}"
                )
                logger.warning(
                    "telegram.callback_failed",
                    action=action,
                    download_id=download_id,
                    error=e.message,
                )
                return

            except Exception as e:
                await query.edit_message_text(
                    f"⚠️ Unexpected error\n\n{query.message.text}"
                )
                logger.error(
                    "telegram.callback_error",
                    action=action,
                    download_id=download_id,
                    error=str(e),
                    exc_info=True,
                )
                return

        logger.info(
            "telegram.callback_handled",
            action=action,
            download_id=download_id,
            user=username,
        )

    def create_approval_keyboard(self, download_id: int) -> InlineKeyboardMarkup:
        """
        Create inline keyboard for download approval

        Args:
            download_id: Pending download ID

        Returns:
            InlineKeyboardMarkup: Telegram inline keyboard
        """
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Approve",
                    callback_data=f"approve:{download_id}",
                ),
                InlineKeyboardButton(
                    "❌ Decline",
                    callback_data=f"decline:{download_id}",
                ),
            ]
        ]

        return InlineKeyboardMarkup(keyboard)

    async def send_approval_request(
        self,
        download_id: int,
        message: str,
    ) -> int | None:
        """
        Send download approval request with inline buttons

        Args:
            download_id: Pending download ID
            message: Approval message text

        Returns:
            int: Telegram message ID or None if failed
        """
        if not self._application or not self.settings.TELEGRAM_ENABLED:
            logger.warning("telegram.not_initialized")
            return None

        try:
            keyboard = self.create_approval_keyboard(download_id)

            # Send message
            telegram_message = await self._application.bot.send_message(
                chat_id=self.settings.TELEGRAM_CHAT_ID,
                text=message,
                reply_markup=keyboard,
                parse_mode="HTML",
            )

            logger.info(
                "telegram.approval_sent",
                download_id=download_id,
                message_id=telegram_message.message_id,
            )

            return telegram_message.message_id

        except Exception as e:
            logger.error(
                "telegram.send_failed",
                download_id=download_id,
                error=str(e),
            )
            return None

    async def edit_message(
        self,
        message_id: int,
        new_text: str,
        remove_keyboard: bool = True,
    ) -> bool:
        """
        Edit an existing message

        Args:
            message_id: Telegram message ID
            new_text: New message text
            remove_keyboard: Remove inline keyboard

        Returns:
            bool: True if edited successfully
        """
        if not self._application or not self.settings.TELEGRAM_ENABLED:
            return False

        try:
            await self._application.bot.edit_message_text(
                chat_id=self.settings.TELEGRAM_CHAT_ID,
                message_id=message_id,
                text=new_text,
                reply_markup=None if remove_keyboard else None,
                parse_mode="HTML",
            )

            logger.info("telegram.message_edited", message_id=message_id)
            return True

        except Exception as e:
            logger.error("telegram.edit_failed", message_id=message_id, error=str(e))
            return False

    async def send_notification(
        self,
        message: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
    ) -> int | None:
        """
        Send a simple notification message

        Args:
            message: Message text
            parse_mode: Parse mode (HTML, Markdown, MarkdownV2)
            disable_notification: Silent notification

        Returns:
            int: Message ID or None if failed
        """
        if not self._application or not self.settings.TELEGRAM_ENABLED:
            return None

        try:
            telegram_message = await self._application.bot.send_message(
                chat_id=self.settings.TELEGRAM_CHAT_ID,
                text=message,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
            )

            return telegram_message.message_id

        except Exception as e:
            logger.error("telegram.notification_failed", error=str(e))
            return None

    def verify_webhook_signature(
        self,
        request_data: bytes,
        signature: str,
    ) -> bool:
        """
        Verify webhook signature from Telegram

        Args:
            request_data: Raw request body
            signature: X-Telegram-Bot-Api-Secret-Token header

        Returns:
            bool: True if signature is valid
        """
        if not self.settings.TELEGRAM_WEBHOOK_SECRET:
            # No secret configured, skip verification
            return True

        expected_signature = hmac.new(
            self.settings.TELEGRAM_WEBHOOK_SECRET.encode(),
            request_data,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    async def health_check(self) -> dict[str, Any]:
        """
        Check Telegram bot health

        Returns:
            dict: Health status
        """
        if not self.settings.TELEGRAM_ENABLED:
            return {
                "is_connected": False,
                "enabled": False,
            }

        if not self._application:
            return {
                "is_connected": False,
                "enabled": True,
                "error": "Not initialized",
            }

        try:
            me = await self._application.bot.get_me()
            return {
                "is_connected": True,
                "enabled": True,
                "bot_username": me.username,
                "bot_id": me.id,
            }

        except Exception as e:
            return {
                "is_connected": False,
                "enabled": True,
                "error": str(e),
            }

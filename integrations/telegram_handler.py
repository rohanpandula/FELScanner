"""
Telegram Interactive Handler

Sends interactive approval requests via Telegram with inline buttons.
Handles user responses and tracks pending downloads.
"""

import logging
import requests
import asyncio
from typing import Dict, Optional, Any, Callable
from datetime import datetime

log = logging.getLogger(__name__)


class TelegramDownloadHandler:
    """Handles interactive Telegram approval workflow"""

    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram handler

        Args:
            bot_token: Telegram bot token
            chat_id: Target chat ID for notifications
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.pending_downloads = {}  # message_id -> download_data
        self.callback_handler: Optional[Callable] = None

    def set_callback_handler(self, handler: Callable):
        """
        Set callback function for button presses

        Args:
            handler: Async function(request_id, action) -> result
        """
        self.callback_handler = handler

    def send_approval_request(self, download_request: Dict[str, Any]) -> Optional[int]:
        """
        Send approval request with inline buttons

        Args:
            download_request: Dict with movie details and upgrade info

        Returns:
            Message ID or None if failed
        """
        try:
            request_id = download_request.get('request_id')
            movie_title = download_request.get('movie_title', 'Unknown Movie')
            year = download_request.get('year', '')
            current_quality = download_request.get('current_quality', 'Unknown')
            new_quality = download_request.get('new_quality', 'Unknown')
            target_folder = download_request.get('target_folder', '')
            upgrade_reason = download_request.get('upgrade_reason', 'Upgrade available')

            # Format message
            message = self._format_approval_message(
                movie_title, year, current_quality, new_quality,
                target_folder, upgrade_reason
            )

            # Create inline keyboard with buttons
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Download", "callback_data": f"dl_yes_{request_id}"},
                        {"text": "❌ Skip", "callback_data": f"dl_no_{request_id}"}
                    ]
                ]
            }

            # Send message
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "reply_markup": keyboard
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get('ok'):
                message_id = result['result']['message_id']

                # Store pending download
                self.pending_downloads[message_id] = {
                    'request_id': request_id,
                    'download_data': download_request,
                    'timestamp': datetime.now()
                }

                log.info(f"Sent approval request for {movie_title} (message_id: {message_id})")
                return message_id
            else:
                log.error(f"Telegram send failed: {result}")
                return None

        except Exception as e:
            log.error(f"Error sending Telegram approval request: {e}")
            return None

    def _format_approval_message(
        self,
        movie_title: str,
        year: Optional[int],
        current_quality: str,
        new_quality: str,
        target_folder: str,
        upgrade_reason: str
    ) -> str:
        """Format approval message with HTML markup"""

        title_with_year = f"{movie_title} ({year})" if year else movie_title

        message = f"🎬 <b>New Version Available!</b>\n\n"
        message += f"<b>Movie:</b> {title_with_year}\n\n"

        message += f"📀 <b>Current Quality:</b>\n{current_quality}\n\n"
        message += f"⭐ <b>New Quality:</b>\n{new_quality}\n\n"

        message += f"💡 <b>Reason:</b> {upgrade_reason}\n\n"

        if target_folder:
            # Shorten folder path for readability
            folder_display = target_folder.split('/')[-1] if '/' in target_folder else target_folder
            message += f"📂 <b>Folder:</b> {folder_display}\n\n"

        message += "Download this version?"

        return message

    def handle_callback(
        self,
        callback_data: str,
        message_id: int,
        chat_id: int,
        callback_query_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle button press from user

        Args:
            callback_data: Callback data from button (e.g., "dl_yes_abc123")
            message_id: Telegram message ID
            chat_id: Chat ID where button was pressed
            callback_query_id: Telegram callback query ID (for answerCallbackQuery)

        Returns:
            Dict with action result
        """
        try:
            # Parse callback data
            parts = callback_data.split('_', 2)
            if len(parts) != 3:
                log.error(f"Invalid callback data: {callback_data}")
                return {'success': False, 'error': 'Invalid callback data'}

            action = parts[1]  # 'yes' or 'no'
            request_id = parts[2]

            # Get pending download info
            pending = self.pending_downloads.get(message_id)
            if not pending:
                log.warning(f"No pending download for message {message_id}")
                return {
                    'success': False,
                    'error': 'Download request expired or already processed'
                }

            download_data = pending['download_data']
            movie_title = download_data.get('movie_title', 'Unknown')

            if action == "yes":
                # User approved download
                log.info(f"User approved download: {movie_title}")

                # Call the callback handler if set
                callback_result = None
                if self.callback_handler:
                    try:
                        callback_response = self.callback_handler(request_id, "approved")
                        if asyncio.iscoroutine(callback_response):
                            callback_result = self._run_coroutine(callback_response)
                        else:
                            callback_result = callback_response
                    except Exception as exc:
                        log.error(f"Callback handler failed for {movie_title}: {exc}", exc_info=True)
                        callback_result = {'success': False, 'error': str(exc)}

                if isinstance(callback_result, dict):
                    result = callback_result
                    result.setdefault('action', 'approved')
                    result.setdefault('request_id', request_id)
                else:
                    result = {'success': True, 'action': 'approved', 'request_id': request_id}

                if result.get('success'):
                    message_text = (
                        f"✅ <b>Download Started</b>\n\n{movie_title}\n\nDownload has been queued."
                    )
                    callback_answer = "Download started! 🚀"
                else:
                    error_text = result.get('error', 'Download could not be started.')
                    message_text = (
                        f"⚠️ <b>Download Failed</b>\n\n{movie_title}\n\n{error_text}"
                    )
                    callback_answer = "Download failed"

                # Update message
                self._update_message(
                    chat_id, message_id,
                    message_text
                )

                # Answer callback query (stop loading animation)
                self._answer_callback_query(callback_query_id, callback_answer)

            else:
                # User declined
                log.info(f"User declined download: {movie_title}")
                result = {'success': True, 'action': 'declined', 'request_id': request_id}

                # Update message
                self._update_message(
                    chat_id, message_id,
                    f"❌ <b>Skipped</b>\n\n{movie_title}\n\nDownload was not queued."
                )

                # Answer callback query
                self._answer_callback_query(callback_query_id, "Skipped")

            # Remove from pending
            del self.pending_downloads[message_id]

            return result

        except Exception as e:
            log.error(f"Error handling callback: {e}")
            return {'success': False, 'error': str(e)}

    def _update_message(self, chat_id: int, message_id: int, new_text: str):
        """Update message text (remove buttons)"""
        try:
            url = f"{self.base_url}/editMessageText"
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": new_text,
                "parse_mode": "HTML"
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
        except Exception as e:
            log.error(f"Error updating message: {e}")

    def _answer_callback_query(self, callback_query_id: Optional[str], text: str):
        """Answer callback query to stop loading animation."""
        if not callback_query_id:
            log.debug("No callback_query_id provided; skipping answerCallbackQuery call")
            return

        try:
            url = f"{self.base_url}/answerCallbackQuery"
            payload = {
                "callback_query_id": callback_query_id,
                "text": text
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
        except Exception as e:
            log.error(f"Error answering callback query: {e}")

    @staticmethod
    def _run_coroutine(coro):
        """Run coroutine to completion using a dedicated event loop."""
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def send_notification(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send simple notification (no buttons)

        Args:
            message: Message text
            parse_mode: Parse mode (HTML or Markdown)

        Returns:
            True if successful
        """
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            return result.get('ok', False)

        except Exception as e:
            log.error(f"Error sending notification: {e}")
            return False

    def send_download_started(self, movie_title: str, quality: str, folder: str):
        """Send notification that download started"""
        message = f"🚀 <b>Download Started</b>\n\n"
        message += f"<b>Movie:</b> {movie_title}\n"
        message += f"<b>Quality:</b> {quality}\n"
        message += f"<b>Folder:</b> {folder}"

        self.send_notification(message)

    def send_download_completed(self, movie_title: str, quality: str):
        """Send notification that download completed"""
        message = f"✅ <b>Download Complete</b>\n\n"
        message += f"<b>Movie:</b> {movie_title}\n"
        message += f"<b>Quality:</b> {quality}\n\n"
        message += "Plex should detect both versions soon!"

        self.send_notification(message)

    def send_download_error(self, movie_title: str, error: str):
        """Send notification about download error"""
        message = f"❌ <b>Download Error</b>\n\n"
        message += f"<b>Movie:</b> {movie_title}\n"
        message += f"<b>Error:</b> {error}"

        self.send_notification(message)

    def test_connection(self) -> Dict[str, Any]:
        """
        Test Telegram bot connection

        Returns:
            Dict with success status and bot info
        """
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get('ok'):
                bot_info = result['result']
                return {
                    'success': True,
                    'bot_username': bot_info.get('username'),
                    'bot_name': bot_info.get('first_name'),
                    'message': f"Connected to @{bot_info.get('username')}"
                }
            else:
                return {'success': False, 'error': 'Bot API returned not ok'}

        except Exception as e:
            log.error(f"Telegram connection test failed: {e}")
            return {'success': False, 'error': str(e)}

    def cleanup_expired(self, max_age_hours: int = 24):
        """
        Clean up expired pending downloads

        Args:
            max_age_hours: Maximum age in hours before expiration
        """
        now = datetime.now()
        expired = []

        for message_id, pending in self.pending_downloads.items():
            age = (now - pending['timestamp']).total_seconds() / 3600
            if age > max_age_hours:
                expired.append(message_id)

        for message_id in expired:
            pending = self.pending_downloads[message_id]
            movie_title = pending['download_data'].get('movie_title', 'Unknown')
            log.info(f"Expired pending download: {movie_title}")
            del self.pending_downloads[message_id]

        return len(expired)

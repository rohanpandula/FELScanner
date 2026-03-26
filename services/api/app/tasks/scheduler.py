"""
Task Scheduler
APScheduler configuration for background jobs
"""
import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.logging import get_logger

logger = get_logger(__name__)


class TaskScheduler:
    """
    Background task scheduler

    Manages all scheduled jobs:
    - Connection health checks (15 min intervals)
    - Periodic library scans (configurable)
    - Monitor cycle (1 min when active)
    - Notification queue processing (1 min)
    - Cleanup expired downloads (hourly)
    """

    def __init__(self):
        """Initialize scheduler"""
        self.settings = get_settings()
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._is_monitoring = False

    async def start(self):
        """Start the scheduler and add all jobs"""
        logger.info("scheduler.starting")

        # Add jobs based on configuration
        await self._add_jobs()

        # Start scheduler
        self.scheduler.start()
        logger.info("scheduler.started")

        # Auto-start based on configuration
        if self.settings.AUTO_START_MODE == "scan":
            logger.info("scheduler.auto_start_scan")
            # Trigger initial scan
            await self._trigger_scan()
        elif self.settings.AUTO_START_MODE == "monitor":
            logger.info("scheduler.auto_start_monitor")
            self._is_monitoring = True

    async def shutdown(self):
        """Shutdown the scheduler gracefully"""
        logger.info("scheduler.shutting_down")
        self.scheduler.shutdown(wait=True)
        logger.info("scheduler.shutdown_complete")

    async def _add_jobs(self):
        """Add all scheduled jobs"""
        # Connection health checks (every 15 minutes)
        self.scheduler.add_job(
            self._check_connections,
            trigger=IntervalTrigger(
                minutes=self.settings.CONNECTION_CHECK_INTERVAL_MINUTES
            ),
            id="connection_checks",
            name="Connection Health Checks",
            replace_existing=True,
        )

        # Periodic library scans (configurable hours)
        if self.settings.SCAN_FREQUENCY_HOURS > 0:
            self.scheduler.add_job(
                self._trigger_scan,
                trigger=IntervalTrigger(hours=self.settings.SCAN_FREQUENCY_HOURS),
                id="periodic_scan",
                name="Periodic Library Scan",
                replace_existing=True,
            )

        # Monitor cycle (every 1 minute when enabled)
        self.scheduler.add_job(
            self._monitor_cycle,
            trigger=IntervalTrigger(
                minutes=self.settings.MONITOR_INTERVAL_MINUTES
            ),
            id="monitor_cycle",
            name="Monitor Cycle",
            replace_existing=True,
        )

        # Process notification queue (every minute)
        if self.settings.TELEGRAM_ENABLED:
            self.scheduler.add_job(
                self._process_notifications,
                trigger=IntervalTrigger(minutes=1),
                id="process_notifications",
                name="Process Notification Queue",
                replace_existing=True,
            )

        # Cleanup expired downloads (hourly)
        self.scheduler.add_job(
            self._cleanup_expired_downloads,
            trigger=IntervalTrigger(hours=1),
            id="cleanup_downloads",
            name="Cleanup Expired Downloads",
            replace_existing=True,
        )

        logger.info("scheduler.jobs_added", job_count=len(self.scheduler.get_jobs()))

    async def _check_connections(self):
        """Check all service connections"""
        logger.debug("scheduler.task.check_connections")

        try:
            from app.integrations.plex.client import PlexClient
            from app.integrations.qbittorrent.client import QBittorrentClient
            from app.integrations.radarr.client import RadarrClient
            from app.integrations.telegram.handler import TelegramHandler

            session_factory = get_session_factory()

            async with session_factory() as db:
                from app.models.connection_status import ConnectionStatus
                from sqlalchemy import select

                # Check Plex
                plex_client = PlexClient()
                plex_connected = await plex_client.connect()

                await self._update_connection_status(
                    db,
                    "plex",
                    plex_connected,
                    "Connected" if plex_connected else "Failed to connect",
                )

                # Check qBittorrent
                if self.settings.QBITTORRENT_HOST:
                    qbit_client = QBittorrentClient()
                    qbit_health = await qbit_client.health_check()

                    await self._update_connection_status(
                        db,
                        "qbittorrent",
                        qbit_health["is_connected"],
                        qbit_health.get("error", "Connected"),
                    )
                    await qbit_client.close()

                # Check Radarr
                if self.settings.RADARR_URL:
                    radarr_client = RadarrClient()
                    radarr_health = await radarr_client.health_check()

                    await self._update_connection_status(
                        db,
                        "radarr",
                        radarr_health["is_connected"],
                        radarr_health.get("error", "Connected"),
                    )
                    await radarr_client.close()

                # Check Telegram
                if self.settings.TELEGRAM_ENABLED:
                    telegram_handler = TelegramHandler()
                    telegram_health = await telegram_handler.health_check()

                    await self._update_connection_status(
                        db,
                        "telegram",
                        telegram_health["is_connected"],
                        telegram_health.get("error", "Connected"),
                    )

                await db.commit()

        except Exception as e:
            logger.error("scheduler.check_connections_failed", error=str(e))

    async def _update_connection_status(
        self,
        db,
        service: str,
        is_connected: bool,
        message: str,
    ):
        """Update connection status in database"""
        from app.models.connection_status import ConnectionStatus
        from sqlalchemy import select

        result = await db.execute(
            select(ConnectionStatus).where(ConnectionStatus.service == service)
        )
        status = result.scalar_one_or_none()

        if status:
            status.is_connected = is_connected
            status.status_message = message
            status.last_checked_at = datetime.now()
            status.total_checks += 1

            if is_connected:
                status.consecutive_failures = 0
                status.last_success_at = datetime.now()
            else:
                status.consecutive_failures += 1
                status.total_failures += 1
                status.last_failure_at = datetime.now()
        else:
            status = ConnectionStatus(
                service=service,
                is_connected=is_connected,
                status_message=message,
                total_checks=1,
                total_failures=0 if is_connected else 1,
                consecutive_failures=0 if is_connected else 1,
                last_success_at=datetime.now() if is_connected else None,
                last_failure_at=datetime.now() if not is_connected else None,
            )
            db.add(status)

    async def _trigger_scan(self):
        """Trigger a library scan"""
        logger.info("scheduler.task.trigger_scan")

        try:
            from app.services.scan_service import ScanService

            session_factory = get_session_factory()

            async with session_factory() as db:
                service = ScanService(db)
                scan = await service.trigger_full_scan(
                    trigger="scheduled",
                    triggered_by="scheduler",
                )
                logger.info("scheduler.scan_triggered", scan_id=scan.id)

        except RuntimeError as e:
            # Scan already running
            logger.warning("scheduler.scan_already_running", error=str(e))
        except Exception as e:
            logger.error("scheduler.scan_failed", error=str(e))

    async def _monitor_cycle(self):
        """Monitor cycle for new DV content"""
        if not self._is_monitoring:
            return

        logger.debug("scheduler.task.monitor_cycle")

        # TODO: Implement monitor logic
        # - Check for new movies in Plex
        # - Check IPT scraper for new torrents
        # - Run upgrade detection
        # - Queue notifications

    async def _process_notifications(self):
        """Process notification queue"""
        logger.debug("scheduler.task.process_notifications")

        try:
            from app.integrations.telegram.notifier import TelegramNotifier

            session_factory = get_session_factory()

            async with session_factory() as db:
                notifier = TelegramNotifier(db)
                sent_count = await notifier.process_pending_notifications()

                if sent_count > 0:
                    logger.info("scheduler.notifications_sent", count=sent_count)

        except Exception as e:
            logger.error("scheduler.process_notifications_failed", error=str(e))

    async def _cleanup_expired_downloads(self):
        """Cleanup expired download requests"""
        logger.debug("scheduler.task.cleanup_downloads")

        try:
            from app.models.download_history import DownloadHistory
            from app.models.pending_download import PendingDownload
            from sqlalchemy import update

            session_factory = get_session_factory()

            async with session_factory() as db:
                # Find expired downloads
                result = await db.execute(
                    select(PendingDownload)
                    .where(PendingDownload.status == "pending")
                    .where(PendingDownload.expires_at <= datetime.now())
                )
                expired = result.scalars().all()

                for download in expired:
                    # Mark as expired
                    download.status = "expired"

                    # Create history record
                    history = DownloadHistory(
                        torrent_id=download.torrent_id,
                        torrent_name=download.torrent_name,
                        movie_title=download.movie_title,
                        movie_year=download.movie_year,
                        movie_rating_key=download.movie_rating_key,
                        action="expired",
                        quality=download.quality,
                        upgrade_type=download.upgrade_type,
                    )
                    db.add(history)

                await db.commit()

                if expired:
                    logger.info("scheduler.downloads_expired", count=len(expired))

        except Exception as e:
            logger.error("scheduler.cleanup_downloads_failed", error=str(e))

    def enable_monitoring(self):
        """Enable monitor mode"""
        self._is_monitoring = True
        logger.info("scheduler.monitoring_enabled")

    def disable_monitoring(self):
        """Disable monitor mode"""
        self._is_monitoring = False
        logger.info("scheduler.monitoring_disabled")

    def get_jobs(self) -> list[dict]:
        """Get all scheduled jobs"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time,
                "trigger": str(job.trigger),
            })
        return jobs

"""
Seed the settings key-value table from env vars on startup.

Only runs when the table is empty — preserves any user-edited values. This
bridges the gap between env-based config and the UI's settings editor so the
Settings screen isn't blank when the user opens it.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.settings import Setting

logger = get_logger(__name__)


def _defaults_from_env(s: Settings) -> list[tuple[str, Any, str, str]]:
    """
    Return a list of (key, value, category, description) tuples derived from
    env-backed settings. Sensitive fields (tokens, passwords) are still stored
    so the UI can show/hide/edit them — the DB is already trusted.
    """
    return [
        # -------- Plex --------
        ("plex_url",          s.PLEX_URL,         "plex", "Plex server URL"),
        ("plex_token",        s.PLEX_TOKEN,       "plex", "Plex auth token"),
        ("plex_library_name", s.LIBRARY_NAME,     "plex", "Plex movies library name"),

        # -------- Telegram --------
        ("telegram_enabled",  s.TELEGRAM_ENABLED, "telegram", "Send Telegram notifications"),
        ("telegram_bot_token", s.TELEGRAM_TOKEN,  "telegram", "Telegram bot token"),
        ("telegram_chat_id",   s.TELEGRAM_CHAT_ID, "telegram", "Telegram chat ID to notify"),

        # -------- qBittorrent --------
        ("qbittorrent_host",     s.QBITTORRENT_HOST,     "qbittorrent", "qBittorrent host"),
        ("qbittorrent_port",     s.QBITTORRENT_PORT,     "qbittorrent", "qBittorrent WebUI port"),
        ("qbittorrent_username", s.QBITTORRENT_USERNAME, "qbittorrent", "qBittorrent username"),
        ("qbittorrent_password", s.QBITTORRENT_PASSWORD, "qbittorrent", "qBittorrent password"),
        ("qbittorrent_category", s.QBITTORRENT_CATEGORY, "qbittorrent", "qBittorrent category for FEL torrents"),

        # -------- Radarr --------
        ("radarr_url",       s.RADARR_URL,       "radarr", "Radarr URL"),
        ("radarr_api_key",   s.RADARR_API_KEY,   "radarr", "Radarr API key"),
        ("radarr_root_path", s.RADARR_ROOT_PATH, "radarr", "Radarr root folder path"),

        # -------- Notifications — safe defaults (bool) --------
        ("notify_fel",                        True,  "notifications", "Notify on any FEL discovery"),
        ("notify_fel_from_p5",                True,  "notifications", "Notify on P5→FEL upgrades"),
        ("notify_fel_from_hdr",               True,  "notifications", "Notify on HDR→FEL upgrades"),
        ("notify_fel_duplicates",             False, "notifications", "Notify on FEL duplicates"),
        ("notify_dv_any",                     False, "notifications", "Notify on any DV"),
        ("notify_dv_upgrades",                True,  "notifications", "Notify on DV profile upgrades"),
        ("notify_atmos_any",                  False, "notifications", "Notify on any Atmos"),
        ("notify_atmos_to_dv",                True,  "notifications", "Notify on Atmos + DV upgrades"),
        ("notify_4k_any",                     False, "notifications", "Notify on any 4K"),
        ("notify_resolution_upgrade",         True,  "notifications", "Notify on resolution upgrades"),
        ("notify_only_library_movies",        True,  "notifications", "Only notify for movies already in library"),
        ("notify_expire_hours",               24,    "notifications", "Pending notification expiry window (hours)"),

        # -------- Collections --------
        ("collection_dv_p7",  "DV FEL Profile 7", "collections", "Name of DV Profile 7 collection in Plex"),
        ("collection_dv_fel", "All Dolby Vision", "collections", "Name of all-DV collection in Plex"),
        ("collection_atmos",  "TrueHD Atmos",     "collections", "Name of Atmos collection in Plex"),

        # -------- Scheduling --------
        ("scan_schedule_enabled",  True,                               "scan", "Run scheduled library scans"),
        ("scan_frequency_hours",   s.SCAN_FREQUENCY_HOURS,             "scan", "Hours between scheduled scans"),
        ("monitor_interval_minutes", s.MONITOR_INTERVAL_MINUTES,       "scan", "Minutes between monitor cycles"),
        ("auto_start_mode",        s.AUTO_START_MODE,                  "scan", "Auto-start mode: disabled/scan/monitor"),
    ]


def _store_value(value: Any) -> tuple[dict[str, Any] | None, str | None]:
    """
    Normalize a Python value into the Setting row's `value` (JSONB) field.
    """
    if value is None:
        return None, None
    if isinstance(value, (bool, int, float)):
        return {"v": value}, None
    if isinstance(value, str):
        return {"v": value}, None
    if isinstance(value, (list, dict)):
        return {"v": value}, None
    return {"v": str(value)}, None


async def seed_settings_if_empty(db: AsyncSession, s: Settings) -> int:
    """
    If the `settings` table has zero rows, populate it with defaults derived
    from env vars. Returns the number of rows inserted (0 if already seeded).
    """
    count = await db.scalar(select(func.count()).select_from(Setting))
    if count and count > 0:
        return 0

    rows = _defaults_from_env(s)
    inserted = 0
    for key, value, category, description in rows:
        json_val, text_val = _store_value(value)
        db.add(
            Setting(
                key=key,
                value=json_val,
                value_text=text_val,
                category=category,
                description=description,
            )
        )
        inserted += 1

    await db.commit()
    logger.info("settings.seeded_from_env", count=inserted)
    return inserted

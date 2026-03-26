"""
Pydantic Settings Configuration
Centralizes all environment variable management with type safety and validation
"""
from typing import Optional, List
from functools import lru_cache
from pydantic import Field, field_validator, model_validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration from environment variables"""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # ============================================================================
    # APPLICATION
    # ============================================================================
    APP_NAME: str = Field(default="FELScanner", description="Application name")
    APP_VERSION: str = Field(default="2.0.0", description="Application version")
    DEBUG: bool = Field(default=False, description="Debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # ============================================================================
    # API
    # ============================================================================
    API_V1_PREFIX: str = Field(default="/api/v1", description="API v1 prefix")
    CORS_ORIGINS: str | List[str] = Field(
        default=["http://localhost:5173"],
        description="CORS allowed origins (comma-separated string or list)"
    )

    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ============================================================================
    # DATABASE
    # ============================================================================
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://felscanner:password@postgres:5432/felscanner",
        description="Async PostgreSQL connection URL"
    )
    DATABASE_POOL_SIZE: int = Field(default=20, ge=5, le=100)
    DATABASE_MAX_OVERFLOW: int = Field(default=10, ge=0, le=50)
    DATABASE_ECHO: bool = Field(default=False, description="Echo SQL queries")

    # ============================================================================
    # REDIS
    # ============================================================================
    REDIS_URL: str = Field(
        default="redis://redis:6379/0",
        description="Redis connection URL"
    )
    REDIS_CACHE_TTL: int = Field(default=300, description="Cache TTL in seconds")

    # ============================================================================
    # PLEX
    # ============================================================================
    PLEX_URL: str = Field(..., description="Plex server URL (required)")
    PLEX_TOKEN: str = Field(..., description="Plex authentication token (required)")
    LIBRARY_NAME: str = Field(default="Movies", description="Plex library name")
    PLEX_TIMEOUT: int = Field(default=30, description="Plex API timeout in seconds")

    @field_validator("PLEX_URL")
    @classmethod
    def validate_plex_url(cls, v: str) -> str:
        """Ensure Plex URL has http/https scheme"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("PLEX_URL must start with http:// or https://")
        return v.rstrip("/")

    # ============================================================================
    # FFPROBE
    # ============================================================================
    FFPROBE_PATH: Optional[str] = Field(
        default="/usr/bin/ffprobe",
        description="Path to ffprobe binary"
    )
    FFPROBE_TIMEOUT: int = Field(default=60, description="ffprobe timeout in seconds")

    # ============================================================================
    # TELEGRAM
    # ============================================================================
    TELEGRAM_ENABLED: bool = Field(default=False, description="Enable Telegram notifications")
    TELEGRAM_TOKEN: Optional[str] = Field(default=None, description="Telegram bot token")
    TELEGRAM_CHAT_ID: Optional[str] = Field(default=None, description="Telegram chat ID")
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description="Secret for webhook validation"
    )
    TELEGRAM_TIMEOUT: int = Field(default=10, description="Telegram API timeout")

    @model_validator(mode='after')
    def validate_telegram_config(self):
        """Validate Telegram is properly configured if enabled"""
        if self.TELEGRAM_ENABLED:
            if not self.TELEGRAM_TOKEN or not self.TELEGRAM_CHAT_ID:
                raise ValueError("TELEGRAM_TOKEN and TELEGRAM_CHAT_ID required when TELEGRAM_ENABLED=true")
        return self

    # ============================================================================
    # QBITTORRENT
    # ============================================================================
    QBITTORRENT_HOST: Optional[str] = Field(default=None, description="qBittorrent host")
    QBITTORRENT_PORT: int = Field(default=8080, ge=1, le=65535)
    QBITTORRENT_USERNAME: str = Field(default="admin", description="qBittorrent username")
    QBITTORRENT_PASSWORD: str = Field(default="", description="qBittorrent password")
    QBITTORRENT_CATEGORY: str = Field(default="movies-fel", description="Download category")
    QBITTORRENT_PAUSE_ON_ADD: bool = Field(default=False, description="Pause downloads on add")
    QBITTORRENT_SEQUENTIAL: bool = Field(default=True, description="Sequential download")
    QBITTORRENT_TIMEOUT: int = Field(default=30, description="qBittorrent API timeout")

    # ============================================================================
    # RADARR
    # ============================================================================
    RADARR_URL: Optional[str] = Field(default=None, description="Radarr API URL")
    RADARR_API_KEY: Optional[str] = Field(default=None, description="Radarr API key")
    RADARR_ROOT_PATH: Optional[str] = Field(default=None, description="Radarr root folder path")
    RADARR_TIMEOUT: int = Field(default=30, description="Radarr API timeout")

    @field_validator("RADARR_URL")
    @classmethod
    def validate_radarr_url(cls, v: Optional[str]) -> Optional[str]:
        """Ensure Radarr URL has http/https scheme if provided"""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("RADARR_URL must start with http:// or https://")
        return v.rstrip("/") if v else None

    # ============================================================================
    # QBITCOPY (download pipeline)
    # ============================================================================
    QBITCOPY_URL: Optional[str] = Field(
        default=None,
        description="qbitcopy service URL for torrent download pipeline"
    )

    # ============================================================================
    # IPT SCRAPER
    # ============================================================================
    IPT_SCRAPER_URL: str = Field(
        default="http://ipt-scraper:3000",
        description="IPT scraper microservice URL"
    )
    IPT_SCRAPER_TIMEOUT: int = Field(default=120, description="IPT scraper timeout")

    # ============================================================================
    # BACKGROUND TASKS
    # ============================================================================
    SCAN_FREQUENCY_HOURS: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours between automatic scans"
    )
    MONITOR_INTERVAL_MINUTES: int = Field(
        default=1,
        ge=1,
        le=60,
        description="Minutes between monitor checks"
    )
    CONNECTION_CHECK_INTERVAL_MINUTES: int = Field(
        default=15,
        ge=5,
        le=120,
        description="Minutes between connection health checks"
    )
    AUTO_START_MODE: str = Field(
        default="none",
        description="Auto-start behavior: none, scan, monitor"
    )

    @field_validator("AUTO_START_MODE")
    @classmethod
    def validate_auto_start_mode(cls, v: str) -> str:
        """Validate auto-start mode"""
        allowed = ["none", "scan", "monitor"]
        if v not in allowed:
            raise ValueError(f"AUTO_START_MODE must be one of: {', '.join(allowed)}")
        return v

    # ============================================================================
    # FILE STORAGE
    # ============================================================================
    DATA_DIR: str = Field(default="/data", description="Data directory path")
    EXPORTS_DIR: str = Field(default="/data/exports", description="Exports directory")
    MAX_REPORTS_SIZE_MB: int = Field(default=500, ge=10, le=10000, description="Max reports size")

    # ============================================================================
    # COLLECTIONS
    # ============================================================================
    COLLECTION_NAME_ALL_DV: str = Field(default="All Dolby Vision", description="DV collection name")
    COLLECTION_NAME_PROFILE7: str = Field(default="DV FEL Profile 7", description="P7 collection name")
    COLLECTION_NAME_TRUEHD_ATMOS: str = Field(default="TrueHD Atmos", description="Atmos collection name")
    COLLECTION_ENABLE_DV: bool = Field(default=True, description="Enable DV collection")
    COLLECTION_ENABLE_P7: bool = Field(default=True, description="Enable P7 collection")
    COLLECTION_ENABLE_ATMOS: bool = Field(default=True, description="Enable Atmos collection")

    # ============================================================================
    # NOTIFICATION RULES (17 rules from original)
    # ============================================================================
    NOTIFY_FEL: bool = Field(default=True, description="Enable FEL notifications")
    NOTIFY_FEL_FROM_P5: bool = Field(default=True, description="Notify P5→P7 FEL upgrades")
    NOTIFY_FEL_FROM_HDR: bool = Field(default=True, description="Notify HDR→P7 FEL upgrades")
    NOTIFY_FEL_DUPLICATES: bool = Field(default=False, description="Notify FEL duplicates")

    NOTIFY_DV: bool = Field(default=False, description="Enable general DV notifications")
    NOTIFY_DV_FROM_HDR: bool = Field(default=True, description="Notify HDR→DV upgrades")
    NOTIFY_DV_PROFILE_UPGRADES: bool = Field(default=True, description="Notify DV profile upgrades")

    NOTIFY_ATMOS: bool = Field(default=False, description="Enable Atmos notifications")
    NOTIFY_ATMOS_ONLY_IF_NO_ATMOS: bool = Field(default=True, description="Only if no current Atmos")
    NOTIFY_ATMOS_WITH_DV_UPGRADE: bool = Field(default=True, description="Atmos + DV combo upgrades")

    NOTIFY_RESOLUTION: bool = Field(default=False, description="Enable resolution notifications")
    NOTIFY_RESOLUTION_ONLY_UPGRADES: bool = Field(default=True, description="Only genuine upgrades")

    NOTIFY_ONLY_LIBRARY_MOVIES: bool = Field(default=True, description="Only notify for library movies")
    NOTIFY_EXPIRE_HOURS: int = Field(default=24, ge=1, le=168, description="Approval expiry hours")

    # ============================================================================
    # MONITORING
    # ============================================================================
    PROMETHEUS_ENABLED: bool = Field(default=True, description="Enable Prometheus metrics")
    SENTRY_DSN: Optional[str] = Field(default=None, description="Sentry error tracking DSN")

    # ============================================================================
    # SECURITY
    # ============================================================================
    SECRET_KEY: str = Field(
        default="felscanner-secret-key-change-in-production",
        description="Secret key for sessions/signing"
    )

    # ============================================================================
    # COMPUTED PROPERTIES
    # ============================================================================

    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.DEBUG

    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return not self.DEBUG

    @property
    def notification_config(self) -> dict:
        """Get all notification rules as dict"""
        return {
            "notify_fel": self.NOTIFY_FEL,
            "notify_fel_from_p5": self.NOTIFY_FEL_FROM_P5,
            "notify_fel_from_hdr": self.NOTIFY_FEL_FROM_HDR,
            "notify_fel_duplicates": self.NOTIFY_FEL_DUPLICATES,
            "notify_dv": self.NOTIFY_DV,
            "notify_dv_from_hdr": self.NOTIFY_DV_FROM_HDR,
            "notify_dv_profile_upgrades": self.NOTIFY_DV_PROFILE_UPGRADES,
            "notify_atmos": self.NOTIFY_ATMOS,
            "notify_atmos_only_if_no_atmos": self.NOTIFY_ATMOS_ONLY_IF_NO_ATMOS,
            "notify_atmos_with_dv_upgrade": self.NOTIFY_ATMOS_WITH_DV_UPGRADE,
            "notify_resolution": self.NOTIFY_RESOLUTION,
            "notify_resolution_only_upgrades": self.NOTIFY_RESOLUTION_ONLY_UPGRADES,
            "notify_only_library_movies": self.NOTIFY_ONLY_LIBRARY_MOVIES,
            "notify_expire_hours": self.NOTIFY_EXPIRE_HOURS,
        }

    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as list"""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return self.CORS_ORIGINS


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Use lru_cache to create singleton
    """
    return Settings()


# Convenience function for getting settings in dependencies
def get_settings_dependency() -> Settings:
    """Dependency injection helper for FastAPI"""
    return get_settings()

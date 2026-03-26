"""
Settings Pydantic Schemas
DTOs for settings management
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class SettingResponse(BaseModel):
    """Schema for settings response"""

    model_config = ConfigDict(from_attributes=True)

    key: str
    value: dict[str, Any] | None
    value_text: str | None
    description: str | None
    category: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    updated_by: str | None


class SettingUpdate(BaseModel):
    """Schema for updating a setting"""

    value: dict[str, Any] | None = None
    value_text: str | None = None
    description: str | None = None
    category: str | None = None
    updated_by: str | None = None


class SettingCreate(BaseModel):
    """Schema for creating a new setting"""

    key: str = Field(..., description="Setting key (unique)")
    value: dict[str, Any] | None = None
    value_text: str | None = None
    description: str | None = None
    category: str | None = None


class NotificationSettings(BaseModel):
    """Schema for notification configuration"""

    notify_fel: bool = True
    notify_fel_from_p5: bool = True
    notify_fel_from_hdr: bool = True
    notify_fel_duplicates: bool = False
    notify_dv: bool = False
    notify_dv_from_hdr: bool = True
    notify_dv_profile_upgrades: bool = True
    notify_atmos: bool = False
    notify_atmos_only_if_no_atmos: bool = True
    notify_atmos_with_dv_upgrade: bool = True
    notify_resolution: bool = False
    notify_resolution_only_upgrades: bool = True
    notify_only_library_movies: bool = True
    notify_expire_hours: int = Field(24, ge=1, le=168)


class CollectionSettings(BaseModel):
    """Schema for collection configuration"""

    collection_name_all_dv: str = "All Dolby Vision"
    collection_name_profile7: str = "DV FEL Profile 7"
    collection_name_truehd_atmos: str = "TrueHD Atmos"
    collection_enable_dv: bool = True
    collection_enable_p7: bool = True
    collection_enable_atmos: bool = True


class BackgroundTaskSettings(BaseModel):
    """Schema for background task configuration"""

    scan_frequency_hours: int = Field(24, ge=1, le=168)
    monitor_interval_minutes: int = Field(1, ge=1, le=60)
    connection_check_interval_minutes: int = Field(15, ge=5, le=120)
    auto_start_mode: str = Field("none", pattern="^(none|scan|monitor)$")

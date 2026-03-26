"""
Download Pydantic Schemas
DTOs for download approval workflow
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class PendingDownloadResponse(BaseModel):
    """Schema for pending download approval request"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    torrent_id: str
    torrent_name: str
    torrent_url: str
    movie_title: str
    movie_year: int | None
    movie_rating_key: str | None
    quality: str | None
    resolution: str | None
    dv_profile: str | None
    has_fel: bool
    has_atmos: bool
    upgrade_type: str | None
    is_upgrade: bool
    is_duplicate: bool
    size_bytes: int | None
    seeders: int | None
    leechers: int | None
    upload_date: datetime | None
    status: str
    telegram_message_id: int | None
    approved_by: str | None
    approved_at: datetime | None
    declined_reason: str | None
    expires_at: datetime
    extra_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    @property
    def is_expired(self) -> bool:
        """Check if download has expired"""
        return datetime.now(self.expires_at.tzinfo) > self.expires_at

    @property
    def is_pending(self) -> bool:
        """Check if still awaiting approval"""
        return self.status == "pending" and not self.is_expired

    @property
    def display_quality(self) -> str:
        """Human-readable quality"""
        parts = []
        if self.resolution:
            parts.append(self.resolution)
        if self.has_fel:
            parts.append("DV P7 FEL")
        elif self.dv_profile:
            parts.append(f"DV {self.dv_profile}")
        if self.has_atmos:
            parts.append("Atmos")
        return " / ".join(parts) if parts else self.quality or "Unknown"


class DownloadApprovalRequest(BaseModel):
    """Schema for approving/declining a download"""

    action: str = Field(..., description="approve or decline")
    reason: str | None = Field(None, description="Reason for action (optional)")
    approved_by: str | None = Field(None, description="Username who approved")


class DownloadHistoryResponse(BaseModel):
    """Schema for download history record"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    torrent_id: str
    torrent_name: str
    movie_title: str
    movie_year: int | None
    movie_rating_key: str | None
    action: str
    action_by: str | None
    action_reason: str | None
    quality: str | None
    upgrade_type: str | None
    qbittorrent_hash: str | None
    radarr_download_id: int | None
    download_started_at: datetime | None
    download_completed_at: datetime | None
    extra_data: dict[str, Any] | None
    created_at: datetime


class PendingDownloadListResponse(BaseModel):
    """Schema for paginated pending downloads list"""

    total: int = Field(..., description="Total pending downloads")
    pending: int = Field(..., description="Actually pending (not expired)")
    expired: int = Field(..., description="Expired count")
    downloads: list[PendingDownloadResponse] = Field(..., description="List of downloads")


class DownloadHistoryListResponse(BaseModel):
    """Schema for paginated download history list"""

    total: int = Field(..., description="Total history records")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")
    history: list[DownloadHistoryResponse] = Field(..., description="List of history")


class DownloadStats(BaseModel):
    """Schema for download statistics"""

    total_downloads: int
    approved: int
    declined: int
    expired: int
    pending: int
    success_rate: float  # percentage
    upgrades_found: int
    duplicates_found: int
    by_upgrade_type: dict[str, int]  # {"P5->P7": 5, "HDR->DV": 3}

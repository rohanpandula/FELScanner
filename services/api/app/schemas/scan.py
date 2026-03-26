"""
Scan Pydantic Schemas
DTOs for scan-related API endpoints
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class ScanTriggerRequest(BaseModel):
    """Schema for triggering a scan"""

    scan_type: str = Field(
        "full",
        description="Type of scan: full, verify, monitor",
    )
    trigger: str = Field(
        "manual",
        description="What triggered the scan: manual, scheduled, webhook",
    )
    triggered_by: str | None = Field(
        None,
        description="User or system that initiated",
    )


class ScanHistoryResponse(BaseModel):
    """Schema for scan history record"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_type: str
    trigger: str
    triggered_by: str | None
    status: str
    error_message: str | None
    movies_scanned: int
    movies_added: int
    movies_updated: int
    movies_removed: int
    dv_discovered: int
    fel_discovered: int
    atmos_discovered: int
    duration_seconds: float | None
    plex_api_calls: int
    ffprobe_calls: int
    collections_updated: int
    extra_data: dict[str, Any] | None
    started_at: datetime
    completed_at: datetime | None


class ScanStatusResponse(BaseModel):
    """Schema for current scan status - matches frontend ScanStatus interface"""

    state: str = Field("idle", description="Current state: idle, scanning, verifying, error")
    progress: int = Field(0, description="Progress percentage 0-100")
    current_movie: str | None = Field(None, description="Currently scanning movie title")
    total_movies: int = Field(0, description="Total movies to scan")
    scanned_count: int = Field(0, description="Movies scanned so far")
    message: str | None = Field(None, description="Status message")
    start_time: datetime | None = Field(None, description="When scan started")
    elapsed_time: int = Field(0, description="Elapsed time in seconds")
    # Additional fields for backward compatibility
    is_running: bool = Field(False, description="Whether a scan is currently running")
    scan_id: int | None = Field(None, description="Current scan ID if running")
    scan_type: str | None = Field(None, description="Type of current scan")
    last_scan: ScanHistoryResponse | None = Field(
        None,
        description="Most recent completed scan",
    )


class ScanHistoryListResponse(BaseModel):
    """Schema for paginated scan history list"""

    total: int = Field(..., description="Total number of scans")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    scans: list[ScanHistoryResponse] = Field(..., description="List of scans")


class ScanProgressUpdate(BaseModel):
    """Schema for real-time scan progress updates"""

    scan_id: int
    status: str
    movies_scanned: int
    total_movies: int
    current_movie: str | None = None
    discoveries: dict[str, int] | None = None  # {"dv": 5, "fel": 2, "atmos": 10}

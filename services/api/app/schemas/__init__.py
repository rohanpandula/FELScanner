"""
Pydantic Schemas (DTOs)
Request and response models for API endpoints
"""
from app.schemas.movie import (
    MovieBase,
    MovieCreate,
    MovieUpdate,
    MovieResponse,
    MovieListResponse,
)
from app.schemas.scan import (
    ScanTriggerRequest,
    ScanStatusResponse,
    ScanHistoryResponse,
)
from app.schemas.download import (
    PendingDownloadResponse,
    DownloadApprovalRequest,
    DownloadHistoryResponse,
)
from app.schemas.settings import (
    SettingResponse,
    SettingUpdate,
)

__all__ = [
    "MovieBase",
    "MovieCreate",
    "MovieUpdate",
    "MovieResponse",
    "MovieListResponse",
    "ScanTriggerRequest",
    "ScanStatusResponse",
    "ScanHistoryResponse",
    "PendingDownloadResponse",
    "DownloadApprovalRequest",
    "DownloadHistoryResponse",
    "SettingResponse",
    "SettingUpdate",
]

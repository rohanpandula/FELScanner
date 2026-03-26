"""
Movie Pydantic Schemas
DTOs for movie-related API endpoints
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class MovieBase(BaseModel):
    """Base movie schema with common fields"""

    title: str = Field(..., description="Movie title")
    year: int | None = Field(None, description="Release year")
    sort_title: str | None = Field(None, description="Sort title")
    original_title: str | None = Field(None, description="Original title")


class MovieCreate(MovieBase):
    """Schema for creating a new movie"""

    rating_key: str = Field(..., description="Plex rating key")
    resolution: str | None = None
    video_codec: str | None = None
    hdr_type: str | None = None
    dv_profile: str | None = None
    dv_fel: bool = False
    dv_bl_compatible: bool = False
    audio_codec: str | None = None
    has_atmos: bool = False
    audio_channels: str | None = None
    file_path: str | None = None
    file_size_bytes: int | None = None
    container: str | None = None
    version_count: int = 1
    best_version_index: int | None = None
    extra_data: dict[str, Any] | None = None


class MovieUpdate(BaseModel):
    """Schema for updating a movie"""

    title: str | None = None
    year: int | None = None
    resolution: str | None = None
    video_codec: str | None = None
    hdr_type: str | None = None
    dv_profile: str | None = None
    dv_fel: bool | None = None
    dv_bl_compatible: bool | None = None
    audio_codec: str | None = None
    has_atmos: bool | None = None
    audio_channels: str | None = None
    file_path: str | None = None
    file_size_bytes: int | None = None
    container: str | None = None
    version_count: int | None = None
    best_version_index: int | None = None
    in_dv_collection: bool | None = None
    in_p7_collection: bool | None = None
    in_atmos_collection: bool | None = None
    extra_data: dict[str, Any] | None = None


class MovieResponse(BaseModel):
    """Schema for movie API response"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rating_key: str
    title: str
    year: int | None
    sort_title: str | None
    original_title: str | None
    resolution: str | None
    video_codec: str | None
    hdr_type: str | None
    dv_profile: str | None
    dv_fel: bool
    dv_bl_compatible: bool
    audio_codec: str | None
    has_atmos: bool
    audio_channels: str | None
    file_path: str | None
    file_size_bytes: int | None
    container: str | None
    version_count: int
    best_version_index: int | None
    in_dv_collection: bool
    in_p7_collection: bool
    in_atmos_collection: bool
    extra_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    last_scanned_at: datetime | None

    # Computed properties
    @property
    def is_dolby_vision(self) -> bool:
        """Check if movie has Dolby Vision"""
        return self.dv_profile is not None and self.dv_profile.startswith("P")

    @property
    def is_fel(self) -> bool:
        """Check if movie has FEL"""
        return self.dv_fel is True

    @property
    def is_4k(self) -> bool:
        """Check if movie is 4K"""
        return self.resolution in ("2160p", "4K")

    @property
    def quality_score(self) -> int:
        """Calculate quality score"""
        score = 0
        if self.is_fel:
            score += 100
        elif self.is_dolby_vision:
            score += 50
        if self.is_4k:
            score += 20
        if self.has_atmos:
            score += 10
        return score

    @property
    def display_quality(self) -> str:
        """Human-readable quality string"""
        parts = []
        if self.resolution:
            parts.append(self.resolution)
        if self.is_fel:
            parts.append("DV P7 FEL")
        elif self.dv_profile:
            parts.append(f"DV {self.dv_profile}")
        elif self.hdr_type and self.hdr_type.lower() != "sdr":
            parts.append(self.hdr_type.upper())
        if self.has_atmos:
            parts.append("Atmos")
        return " / ".join(parts) if parts else "Unknown"


class MovieListResponse(BaseModel):
    """Schema for paginated movie list response"""

    total: int = Field(..., description="Total number of movies")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    movies: list[MovieResponse] = Field(..., description="List of movies")


class MovieFilter(BaseModel):
    """Schema for filtering movies"""

    title: str | None = Field(None, description="Filter by title (partial match)")
    year: int | None = Field(None, description="Filter by year")
    dv_profile: str | None = Field(None, description="Filter by DV profile (P4-P9)")
    dv_fel: bool | None = Field(None, description="Filter by FEL status")
    has_atmos: bool | None = Field(None, description="Filter by Atmos")
    resolution: str | None = Field(None, description="Filter by resolution")
    in_dv_collection: bool | None = Field(None, description="In DV collection")
    in_p7_collection: bool | None = Field(None, description="In P7 collection")
    in_atmos_collection: bool | None = Field(None, description="In Atmos collection")
    sort_by: str = Field("title", description="Sort field")
    sort_order: str = Field("asc", description="Sort order (asc/desc)")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=500, description="Items per page")

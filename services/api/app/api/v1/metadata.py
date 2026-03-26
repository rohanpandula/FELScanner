"""
Metadata API Endpoints
FFProbe metadata and movie version details
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.metadata_cache import MetadataCache
from app.models.movie import Movie
from app.services.metadata_service import refresh_metadata

router = APIRouter()
logger = get_logger(__name__)


@router.get("/movie/{movie_id}", response_model=dict[str, Any])
async def get_movie_metadata_by_id(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed metadata for a movie by ID

    Returns comprehensive movie information including:
    - All versions
    - Video/audio streams
    - FFProbe data (if cached)
    - Quality information
    """
    # Get movie
    result = await db.execute(
        select(Movie).where(Movie.id == movie_id)
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    # Get cached metadata if available
    cache_result = await db.execute(
        select(MetadataCache).where(MetadataCache.rating_key == movie.rating_key)
    )
    cached_metadata = cache_result.scalar_one_or_none()

    response = {
        "id": movie.id,
        "rating_key": movie.rating_key,
        "title": movie.title,
        "year": movie.year,
        "quality": movie.display_quality if hasattr(movie, 'display_quality') else None,
        "resolution": movie.resolution,
        "codec": movie.video_codec,
        "dv_profile": movie.dv_profile,
        "dv_fel": movie.dv_fel,
        "has_atmos": movie.has_atmos,
        "file_path": movie.file_path,
        "file_size": movie.file_size_bytes,
        "quality_info": {
            "resolution": movie.resolution,
            "video_codec": movie.video_codec,
            "hdr_type": movie.hdr_type,
            "dv_profile": movie.dv_profile,
            "dv_fel": movie.dv_fel,
            "dv_bl_compatible": movie.dv_bl_compatible,
            "audio_codec": movie.audio_codec,
            "has_atmos": movie.has_atmos,
            "audio_channels": movie.audio_channels,
            "display_quality": movie.display_quality if hasattr(movie, 'display_quality') else None,
            "quality_score": movie.quality_score if hasattr(movie, 'quality_score') else None,
        },
        "file": {
            "path": movie.file_path,
            "size_bytes": movie.file_size_bytes,
            "container": movie.container,
        },
        "versions": {
            "count": movie.version_count if hasattr(movie, 'version_count') else 1,
            "best_index": movie.best_version_index if hasattr(movie, 'best_version_index') else 0,
            "all_versions": movie.extra_data.get("versions", []) if movie.extra_data else [],
        },
        "collections": {
            "in_dv_collection": movie.in_dv_collection if hasattr(movie, 'in_dv_collection') else False,
            "in_p7_collection": movie.in_p7_collection if hasattr(movie, 'in_p7_collection') else False,
            "in_atmos_collection": movie.in_atmos_collection if hasattr(movie, 'in_atmos_collection') else False,
        },
        "metadata_cache": None,
    }

    if cached_metadata:
        response["metadata_cache"] = {
            "cached_at": cached_metadata.updated_at,
            "expires_at": cached_metadata.expires_at,
            "is_stale": cached_metadata.is_stale,
            "is_expired": cached_metadata.is_expired,
            "ffprobe_data": cached_metadata.ffprobe_data,
            "video_streams": cached_metadata.video_streams,
            "audio_streams": cached_metadata.audio_streams,
            "subtitle_streams": cached_metadata.subtitle_streams,
        }

    return response


@router.get("/{rating_key}", response_model=dict[str, Any])
async def get_movie_metadata(
    rating_key: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed metadata for a movie by rating key

    Returns comprehensive movie information including:
    - All versions
    - Video/audio streams
    - FFProbe data (if cached)
    - Quality information
    """
    # Get movie
    result = await db.execute(
        select(Movie).where(Movie.rating_key == rating_key)
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    # Get cached metadata if available
    cache_result = await db.execute(
        select(MetadataCache).where(MetadataCache.rating_key == rating_key)
    )
    cached_metadata = cache_result.scalar_one_or_none()

    response = {
        "rating_key": movie.rating_key,
        "title": movie.title,
        "year": movie.year,
        "quality": {
            "resolution": movie.resolution,
            "video_codec": movie.video_codec,
            "hdr_type": movie.hdr_type,
            "dv_profile": movie.dv_profile,
            "dv_fel": movie.dv_fel,
            "dv_bl_compatible": movie.dv_bl_compatible,
            "audio_codec": movie.audio_codec,
            "has_atmos": movie.has_atmos,
            "audio_channels": movie.audio_channels,
            "display_quality": movie.display_quality,
            "quality_score": movie.quality_score,
        },
        "file": {
            "path": movie.file_path,
            "size_bytes": movie.file_size_bytes,
            "container": movie.container,
        },
        "versions": {
            "count": movie.version_count,
            "best_index": movie.best_version_index,
            "all_versions": movie.extra_data.get("versions", []) if movie.extra_data else [],
        },
        "collections": {
            "in_dv_collection": movie.in_dv_collection,
            "in_p7_collection": movie.in_p7_collection,
            "in_atmos_collection": movie.in_atmos_collection,
        },
        "metadata_cache": None,
    }

    if cached_metadata:
        response["metadata_cache"] = {
            "cached_at": cached_metadata.updated_at,
            "expires_at": cached_metadata.expires_at,
            "is_stale": cached_metadata.is_stale,
            "is_expired": cached_metadata.is_expired,
            "ffprobe_data": cached_metadata.ffprobe_data,
            "video_streams": cached_metadata.video_streams,
            "audio_streams": cached_metadata.audio_streams,
            "subtitle_streams": cached_metadata.subtitle_streams,
        }

    return response


@router.post("/movie/{movie_id}/refresh")
async def refresh_metadata_by_id(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh metadata for a specific movie by ID

    Triggers a new scan of the movie to update all metadata.
    """
    # Get movie
    result = await db.execute(
        select(Movie).where(Movie.id == movie_id)
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    try:
        cache = await refresh_metadata(db, movie)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (TimeoutError, RuntimeError) as e:
        raise HTTPException(status_code=500, detail=f"ffprobe failed: {e}")

    logger.info("metadata.refresh_complete", movie_id=movie_id, rating_key=movie.rating_key)

    return {
        "success": True,
        "rating_key": movie.rating_key,
        "cached_at": cache.updated_at,
        "expires_at": cache.expires_at,
        "video_streams": cache.video_streams,
        "audio_streams": cache.audio_streams,
        "subtitle_streams": cache.subtitle_streams,
    }


@router.post("/{rating_key}/refresh")
async def refresh_metadata(
    rating_key: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh metadata for a specific movie by rating key

    Triggers a new scan of the movie to update all metadata.
    """
    # Get movie
    result = await db.execute(
        select(Movie).where(Movie.rating_key == rating_key)
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    try:
        cache = await refresh_metadata(db, movie)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (TimeoutError, RuntimeError) as e:
        raise HTTPException(status_code=500, detail=f"ffprobe failed: {e}")

    logger.info("metadata.refresh_complete", rating_key=rating_key)

    return {
        "success": True,
        "rating_key": movie.rating_key,
        "cached_at": cache.updated_at,
        "expires_at": cache.expires_at,
        "video_streams": cache.video_streams,
        "audio_streams": cache.audio_streams,
        "subtitle_streams": cache.subtitle_streams,
    }


@router.get("/{rating_key}/versions", response_model=list[dict[str, Any]])
async def get_movie_versions(
    rating_key: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all versions of a movie

    Returns detailed information about each version including quality scores.
    """
    # Get movie
    result = await db.execute(
        select(Movie).where(Movie.rating_key == rating_key)
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    versions = movie.extra_data.get("versions", []) if movie.extra_data else []

    # TODO: Parse and enhance version data
    # For now, return raw version data

    return versions


@router.delete("/{rating_key}/cache")
async def clear_metadata_cache(
    rating_key: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Clear cached metadata for a movie

    Forces metadata to be re-fetched on next request.
    """
    result = await db.execute(
        select(MetadataCache).where(MetadataCache.rating_key == rating_key)
    )
    cached = result.scalar_one_or_none()

    if not cached:
        raise HTTPException(status_code=404, detail="No cached metadata found")

    await db.delete(cached)
    await db.commit()

    logger.info("metadata.cache_cleared", rating_key=rating_key)

    return {"success": True, "message": "Metadata cache cleared"}

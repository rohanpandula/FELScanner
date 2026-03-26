"""
Metadata Service
FFProbe execution and metadata cache management
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.metadata_cache import MetadataCache
from app.models.movie import Movie

logger = get_logger(__name__)


async def run_ffprobe(
    file_path: str,
    ffprobe_path: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """
    Run ffprobe on a media file and return parsed output.

    Args:
        file_path: Path to the media file
        ffprobe_path: Path to ffprobe binary (defaults to settings)
        timeout: Timeout in seconds (defaults to settings)

    Returns:
        dict with keys: ffprobe_data, video_streams, audio_streams, subtitle_streams

    Raises:
        FileNotFoundError: If ffprobe binary or media file not accessible
        TimeoutError: If ffprobe exceeds timeout
        RuntimeError: If ffprobe returns non-zero exit code
    """
    settings = get_settings()
    ffprobe_path = ffprobe_path or settings.FFPROBE_PATH
    timeout = timeout or settings.FFPROBE_TIMEOUT

    if not ffprobe_path:
        raise FileNotFoundError("FFPROBE_PATH is not configured")

    proc = await asyncio.create_subprocess_exec(
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        file_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise TimeoutError(f"ffprobe timed out after {timeout}s for {file_path}")

    if proc.returncode != 0:
        error_msg = stderr.decode().strip() if stderr else "Unknown error"
        raise RuntimeError(f"ffprobe failed (exit {proc.returncode}): {error_msg}")

    ffprobe_data = json.loads(stdout.decode())

    # Split streams by codec_type
    streams = ffprobe_data.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

    return {
        "ffprobe_data": ffprobe_data,
        "video_streams": video_streams,
        "audio_streams": audio_streams,
        "subtitle_streams": subtitle_streams,
    }


async def refresh_metadata(
    db: AsyncSession,
    movie: Movie,
) -> MetadataCache:
    """
    Run ffprobe on a movie's file and upsert the metadata cache.

    Args:
        db: Database session
        movie: Movie ORM object (must have file_path and rating_key)

    Returns:
        MetadataCache record (created or updated)

    Raises:
        ValueError: If movie has no file_path
        FileNotFoundError: If ffprobe is not configured
    """
    if not movie.file_path:
        raise ValueError(f"Movie {movie.title} has no file_path")

    logger.info(
        "metadata.refresh_start",
        rating_key=movie.rating_key,
        title=movie.title,
        file_path=movie.file_path,
    )

    probe_result = await run_ffprobe(movie.file_path)

    # Check for existing cache entry
    result = await db.execute(
        select(MetadataCache).where(MetadataCache.rating_key == movie.rating_key)
    )
    cache = result.scalar_one_or_none()

    settings = get_settings()
    ttl = getattr(settings, "METADATA_CACHE_TTL", 86400)
    expires_at = datetime.now() + timedelta(seconds=ttl)

    if cache:
        cache.file_path = movie.file_path
        cache.file_size_bytes = movie.file_size_bytes
        cache.ffprobe_data = probe_result["ffprobe_data"]
        cache.video_streams = probe_result["video_streams"]
        cache.audio_streams = probe_result["audio_streams"]
        cache.subtitle_streams = probe_result["subtitle_streams"]
        cache.is_stale = False
        cache.expires_at = expires_at
    else:
        cache = MetadataCache(
            rating_key=movie.rating_key,
            file_path=movie.file_path,
            file_size_bytes=movie.file_size_bytes,
            ffprobe_data=probe_result["ffprobe_data"],
            video_streams=probe_result["video_streams"],
            audio_streams=probe_result["audio_streams"],
            subtitle_streams=probe_result["subtitle_streams"],
            is_stale=False,
            ttl_seconds=ttl,
            expires_at=expires_at,
        )
        db.add(cache)

    await db.commit()
    await db.refresh(cache)

    logger.info(
        "metadata.refresh_complete",
        rating_key=movie.rating_key,
        video_streams=len(probe_result["video_streams"]),
        audio_streams=len(probe_result["audio_streams"]),
    )

    return cache

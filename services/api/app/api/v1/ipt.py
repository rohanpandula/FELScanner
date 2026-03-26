"""
IPT Scanner API Endpoints
Trigger scans, view cached torrents, manage IPT integration
"""
from typing import Any, AsyncGenerator

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.ipt_service import IPTService

router = APIRouter()
logger = get_logger(__name__)


@router.get("/cache", response_model=list[dict[str, Any]])
async def get_cached_torrents():
    """
    Get cached IPT torrents

    Returns list of known torrents from the scraper cache.
    """
    service = IPTService()
    try:
        torrents = await service.get_known_torrents()
        logger.info("ipt.cache_retrieved", count=len(torrents))
        return torrents
    except Exception as e:
        logger.error("ipt.cache_retrieval_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve cache: {str(e)}")


@router.get("/results", response_model=dict[str, Any])
async def get_scan_results(db: AsyncSession = Depends(get_db)):
    """
    Get latest IPT scan results

    Returns the most recent scan results with all torrents found,
    enriched with library match information.
    """
    service = IPTService(db=db)
    try:
        results = await service.get_latest_results()
        return results
    except Exception as e:
        logger.error("ipt.results_retrieval_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get results: {str(e)}")


@router.post("/scan", response_model=dict[str, Any])
async def trigger_scan():
    """
    Trigger IPT scan

    Triggers a new scan of IPTorrents and returns the results.
    This may take 30-60 seconds to complete.
    """
    service = IPTService()
    try:
        results = await service.trigger_scan()
        return results
    except Exception as e:
        logger.error("ipt.scan_trigger_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger scan: {str(e)}")


async def _stream_scan_logs() -> AsyncGenerator[bytes, None]:
    """Stream SSE events from IPT scraper"""
    settings = get_settings()
    scraper_url = f"{settings.IPT_SCRAPER_URL}/api/scan/stream"

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("GET", scraper_url) as response:
            # Stream raw bytes to preserve SSE format
            async for chunk in response.aiter_bytes():
                yield chunk


@router.get("/scan/stream")
async def trigger_scan_stream():
    """
    Trigger IPT scan with SSE streaming logs

    Returns a Server-Sent Events stream with real-time log messages
    during the scan process. Use this for manual scans to see progress.
    """
    logger.info("ipt.scan_stream_triggered")

    return StreamingResponse(
        _stream_scan_logs(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.post("/cache/clear", response_model=dict[str, str])
async def clear_cache():
    """
    Clear IPT cache

    Clears the known torrents cache, forcing all torrents to be treated as new on next scan.
    """
    service = IPTService()
    try:
        result = await service.clear_cache()
        return result
    except Exception as e:
        logger.error("ipt.cache_clear_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/health", response_model=dict[str, Any])
async def check_health():
    """
    Check IPT scraper service health

    Returns health status of the IPT scraper microservice.
    """
    service = IPTService()
    health = await service.check_health()
    return health


class DownloadRequest(BaseModel):
    """Request to download a torrent via qbitcopy pipeline"""
    title: str
    year: int | None = None
    download_url: str
    in_radarr: bool = False


@router.post("/download", response_model=dict[str, Any])
async def download_torrent(req: DownloadRequest):
    """
    Download a torrent via qbitcopy.

    If movie is not in Radarr, adds it first via Radarr API,
    then sends torrent to qbitcopy for download to the correct path.
    """
    settings = get_settings()

    if not settings.QBITCOPY_URL:
        raise HTTPException(status_code=400, detail="QBITCOPY_URL not configured")

    radarr_url = settings.RADARR_URL
    radarr_key = settings.RADARR_API_KEY
    if not radarr_url or not radarr_key:
        raise HTTPException(status_code=400, detail="Radarr not configured")

    movie_path = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Find or add movie in Radarr
        if not req.in_radarr:
            # Look up movie via Radarr
            lookup_resp = await client.get(
                f"{radarr_url}/api/v3/movie/lookup",
                params={"term": req.title},
                headers={"X-Api-Key": radarr_key},
            )
            if lookup_resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to search Radarr")

            candidates = lookup_resp.json()
            # Match by year if available
            match = None
            for c in candidates:
                if req.year and c.get("year") == req.year:
                    match = c
                    break
            if not match and candidates:
                match = candidates[0]

            if not match:
                raise HTTPException(
                    status_code=404,
                    detail=f"Could not find '{req.title}' in Radarr lookup"
                )

            # Get root folder
            root_resp = await client.get(
                f"{radarr_url}/api/v3/rootfolder",
                headers={"X-Api-Key": radarr_key},
            )
            root_folders = root_resp.json() if root_resp.status_code == 200 else []
            root_path = root_folders[0]["path"] if root_folders else "/movies"

            # Get quality profiles
            qp_resp = await client.get(
                f"{radarr_url}/api/v3/qualityprofile",
                headers={"X-Api-Key": radarr_key},
            )
            profiles = qp_resp.json() if qp_resp.status_code == 200 else []
            quality_profile_id = profiles[0]["id"] if profiles else 1

            # Add to Radarr
            add_payload = {
                "title": match.get("title", req.title),
                "year": match.get("year", req.year),
                "tmdbId": match.get("tmdbId"),
                "titleSlug": match.get("titleSlug"),
                "images": match.get("images", []),
                "qualityProfileId": quality_profile_id,
                "rootFolderPath": root_path,
                "monitored": True,
                "addOptions": {"searchForMovie": False},
            }

            add_resp = await client.post(
                f"{radarr_url}/api/v3/movie",
                json=add_payload,
                headers={"X-Api-Key": radarr_key},
            )

            if add_resp.status_code in (200, 201):
                added = add_resp.json()
                movie_path = added.get("path") or added.get("folderName")
                logger.info("ipt.radarr_added", title=req.title, path=movie_path)
            elif add_resp.status_code == 400:
                # Might already exist — extract path from error or search existing
                error_body = add_resp.json()
                logger.warning("ipt.radarr_add_conflict", detail=str(error_body))
                # Fall through to find existing
            else:
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to add movie to Radarr: {add_resp.status_code}"
                )

        # If we still don't have the path, find it from existing Radarr movies
        if not movie_path:
            movies_resp = await client.get(
                f"{radarr_url}/api/v3/movie",
                headers={"X-Api-Key": radarr_key},
            )
            if movies_resp.status_code == 200:
                all_movies = movies_resp.json()
                title_lower = req.title.lower().strip()
                for m in all_movies:
                    m_title = (m.get("title") or "").lower().strip()
                    m_year = m.get("year")
                    if m_title == title_lower and (not req.year or m_year == req.year):
                        movie_path = m.get("path") or m.get("folderName")
                        break
                    # Also check alternate titles
                    for alt in m.get("alternateTitles", []):
                        if (alt.get("title") or "").lower().strip() == title_lower:
                            movie_path = m.get("path") or m.get("folderName")
                            break
                    if movie_path:
                        break

        if not movie_path:
            raise HTTPException(
                status_code=404,
                detail=f"Could not determine movie path for '{req.title}'"
            )

        # Step 2: Send to qbitcopy for download
        qbitcopy_resp = await client.post(
            f"{settings.QBITCOPY_URL}/api/download",
            json={
                "moviePath": movie_path,
                "downloadUrl": req.download_url,
            },
        )

        if qbitcopy_resp.status_code != 200:
            error_detail = "Unknown error"
            try:
                error_detail = qbitcopy_resp.json().get("error", error_detail)
            except Exception:
                error_detail = qbitcopy_resp.text[:200]
            raise HTTPException(
                status_code=502,
                detail=f"qbitcopy download failed: {error_detail}"
            )

        result = qbitcopy_resp.json()
        logger.info(
            "ipt.download_sent",
            title=req.title,
            path=movie_path,
            added_to_radarr=not req.in_radarr,
        )

        return {
            "success": True,
            "message": result.get("message", "Torrent added"),
            "movie_path": movie_path,
            "added_to_radarr": not req.in_radarr,
        }

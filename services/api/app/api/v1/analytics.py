"""
Analytics API Endpoints
Library quality report, storage analytics, duplicates, upgrade opportunities, comparisons
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.services.analytics_service import AnalyticsService

router = APIRouter()
logger = get_logger(__name__)


# ------------------------------------------------------------------
# Feature 1: Quality Report / Library Health
# ------------------------------------------------------------------

@router.get("/quality-report")
async def get_quality_report(db: AsyncSession = Depends(get_db)):
    """
    Library quality report with health score.

    Returns:
    - health_score: 0-100 overall library quality rating
    - quality_tiers: Movie counts by quality tier (reference/excellent/great/good/acceptable/needs_upgrade)
    - hdr_distribution: Breakdown by HDR type
    - audio_distribution: Breakdown by audio codec
    - resolution_distribution: Breakdown by resolution
    - profile_breakdown: DV profile counts
    - quality_summary: Key percentages (DV%, FEL%, Atmos%, 4K%)
    """
    service = AnalyticsService(db)
    return await service.get_quality_report()


# ------------------------------------------------------------------
# Feature 2: Upgrade Opportunities
# ------------------------------------------------------------------

@router.get("/upgrade-opportunities")
async def get_upgrade_opportunities(db: AsyncSession = Depends(get_db)):
    """
    Movies that could benefit from an upgrade.

    Returns movies sorted by upgrade potential with possible improvements listed.
    """
    service = AnalyticsService(db)
    return await service.get_upgrade_opportunities()


# ------------------------------------------------------------------
# Feature 4: Duplicate Management
# ------------------------------------------------------------------

@router.get("/duplicates")
async def get_duplicates(db: AsyncSession = Depends(get_db)):
    """
    Find movies with multiple versions or duplicate entries.

    Returns multi-version movies and title duplicates with version comparison.
    """
    service = AnalyticsService(db)
    return await service.get_duplicates()


# ------------------------------------------------------------------
# Feature 5: Storage Analytics
# ------------------------------------------------------------------

@router.get("/storage")
async def get_storage_analytics(db: AsyncSession = Depends(get_db)):
    """
    Storage breakdown by resolution, DV status, audio, and codec.

    Includes top largest movies and smallest DV movies.
    """
    service = AnalyticsService(db)
    return await service.get_storage_analytics()


# ------------------------------------------------------------------
# Feature 7: Comparison View
# ------------------------------------------------------------------

class CompareRequest(BaseModel):
    """Request body for movie/torrent comparison"""
    torrent_metadata: dict[str, Any]


@router.post("/compare/{movie_id}")
async def compare_movie_with_torrent(
    movie_id: int,
    request: CompareRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Side-by-side comparison of current movie quality vs a torrent.

    Returns detailed comparison with upgrade details and score difference.
    """
    service = AnalyticsService(db)
    result = await service.compare_movie_with_torrent(
        movie_id, request.torrent_metadata
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result

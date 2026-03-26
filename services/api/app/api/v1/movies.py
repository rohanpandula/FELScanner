"""
Movies API Endpoints
List, filter, search movies
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.schemas.movie import MovieFilter, MovieListResponse, MovieResponse
from app.services.movie_service import MovieService

router = APIRouter()
logger = get_logger(__name__)


@router.get("", response_model=MovieListResponse)
@router.get("/", response_model=MovieListResponse, include_in_schema=False)
async def list_movies(
    title: str | None = Query(None, description="Filter by title (partial match)"),
    year: int | None = Query(None, description="Filter by year"),
    dv_profile: str | None = Query(None, description="Filter by DV profile"),
    dv_fel: bool | None = Query(None, description="Filter by FEL status"),
    has_atmos: bool | None = Query(None, description="Filter by Atmos"),
    resolution: str | None = Query(None, description="Filter by resolution"),
    in_dv_collection: bool | None = Query(None, description="In DV collection"),
    in_p7_collection: bool | None = Query(None, description="In P7 collection"),
    in_atmos_collection: bool | None = Query(None, description="In Atmos collection"),
    sort_by: str = Query("title", description="Sort field"),
    sort_order: str = Query("asc", description="Sort order (asc/desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    List movies with filtering, sorting, and pagination

    Returns paginated list of movies with comprehensive metadata.
    Supports filtering by title, year, DV profile, FEL, Atmos, resolution, and collections.
    """
    # Build filter params
    filter_params = MovieFilter(
        title=title,
        year=year,
        dv_profile=dv_profile,
        dv_fel=dv_fel,
        has_atmos=has_atmos,
        resolution=resolution,
        in_dv_collection=in_dv_collection,
        in_p7_collection=in_p7_collection,
        in_atmos_collection=in_atmos_collection,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    service = MovieService(db)
    movies, total = await service.get_movies(filter_params)

    return MovieListResponse(
        total=total,
        page=page,
        page_size=page_size,
        movies=movies,
    )


@router.get("/statistics", response_model=dict[str, Any])
@router.get("/stats/summary", response_model=dict[str, Any], include_in_schema=False)
async def get_movie_statistics(db: AsyncSession = Depends(get_db)):
    """
    Get library statistics

    Returns counts and breakdowns:
    - Total movies
    - Dolby Vision count
    - FEL (P7) count
    - TrueHD Atmos count
    - 4K count
    - DV profile breakdown (P4, P5, P7, P8, P9)
    """
    service = MovieService(db)
    stats = await service.get_statistics()
    return stats


@router.get("/search/query", response_model=list[MovieResponse])
async def search_movies(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search movies by title

    Returns matching movies ordered by title.
    """
    service = MovieService(db)
    movies = await service.search_movies(q, limit)
    return movies


@router.get("/rating-key/{rating_key}", response_model=MovieResponse)
@router.get("/rating_key/{rating_key}", response_model=MovieResponse, include_in_schema=False)
async def get_movie_by_rating_key(
    rating_key: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific movie by Plex rating key

    Returns full movie details including all metadata and versions.
    """
    service = MovieService(db)
    movie = await service.get_movie_by_rating_key(rating_key)

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    return movie


@router.get("/{movie_id}", response_model=MovieResponse)
async def get_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific movie by ID

    Returns full movie details including all metadata and versions.
    """
    service = MovieService(db)
    movie = await service.get_movie_by_id(movie_id)

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    return movie

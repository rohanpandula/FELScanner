"""
Collections API Endpoints
Plex collection management
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.integrations.plex.collection_manager import CollectionManager
from app.models.collection_change import CollectionChange
from app.models.movie import Movie

router = APIRouter()
logger = get_logger(__name__)


@router.get("/summary", response_model=dict[str, Any])
async def get_collections_summary(db: AsyncSession = Depends(get_db)):
    """
    Get collection summary statistics

    Returns counts of movies in each collection.
    """
    # DV collection count
    dv_result = await db.execute(
        select(func.count())
        .select_from(Movie)
        .where(Movie.in_dv_collection == True)
    )
    dv_count = dv_result.scalar() or 0

    # P7 collection count
    p7_result = await db.execute(
        select(func.count())
        .select_from(Movie)
        .where(Movie.in_p7_collection == True)
    )
    p7_count = p7_result.scalar() or 0

    # Atmos collection count
    atmos_result = await db.execute(
        select(func.count())
        .select_from(Movie)
        .where(Movie.in_atmos_collection == True)
    )
    atmos_count = atmos_result.scalar() or 0

    return {
        "all_dolby_vision": dv_count,
        "dv_fel_profile7": p7_count,
        "truehd_atmos": atmos_count,
    }


@router.post("/verify", response_model=dict[str, int])
async def verify_collections(db: AsyncSession = Depends(get_db)):
    """
    Verify and fix collection memberships

    Ensures all movies are in the correct collections:
    - Adds movies that should be in collections
    - Removes movies that shouldn't be in collections

    Returns statistics about changes made.
    """
    # Get all movies
    result = await db.execute(select(Movie))
    movies = result.scalars().all()

    # Convert to dictionaries for collection manager
    movie_data = []
    for movie in movies:
        movie_data.append({
            "rating_key": movie.rating_key,
            "title": movie.title,
            "year": movie.year,
            "dv_profile": movie.dv_profile,
            "dv_fel": movie.dv_fel,
            "has_atmos": movie.has_atmos,
            "in_dv_collection": movie.in_dv_collection,
            "in_p7_collection": movie.in_p7_collection,
            "in_atmos_collection": movie.in_atmos_collection,
        })

    # Verify collections
    manager = CollectionManager()
    stats = await manager.verify_collections(movie_data)

    logger.info("collections.verified", stats=stats)

    return stats


@router.post("/{collection_type}/add/{rating_key}")
async def add_to_collection(
    collection_type: str,
    rating_key: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually add a movie to a collection

    Collection types: dv, p7, atmos
    """
    # Get movie
    result = await db.execute(
        select(Movie).where(Movie.rating_key == rating_key)
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    manager = CollectionManager()

    # Add to appropriate collection
    if collection_type == "dv":
        success = await manager.add_to_dv_collection(rating_key, movie.title)
        if success:
            movie.in_dv_collection = True
    elif collection_type == "p7":
        success = await manager.add_to_p7_collection(rating_key, movie.title)
        if success:
            movie.in_p7_collection = True
    elif collection_type == "atmos":
        success = await manager.add_to_atmos_collection(rating_key, movie.title)
        if success:
            movie.in_atmos_collection = True
    else:
        raise HTTPException(status_code=400, detail="Invalid collection type")

    if not success:
        raise HTTPException(status_code=500, detail="Failed to add to collection")

    # Record change
    change = CollectionChange(
        collection_name=f"{collection_type.upper()} Collection",
        collection_type=collection_type,
        movie_rating_key=rating_key,
        movie_title=movie.title,
        movie_year=movie.year,
        action="added",
        reason="Manual addition via API",
        triggered_by="api",
    )
    db.add(change)

    await db.commit()

    return {"success": True, "message": f"Added to {collection_type} collection"}


@router.delete("/{collection_type}/remove/{rating_key}")
async def remove_from_collection(
    collection_type: str,
    rating_key: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually remove a movie from a collection

    Collection types: dv, p7, atmos
    """
    # Get movie
    result = await db.execute(
        select(Movie).where(Movie.rating_key == rating_key)
    )
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    manager = CollectionManager()

    # Remove from appropriate collection
    if collection_type == "dv":
        success = await manager.remove_from_dv_collection(rating_key, movie.title)
        if success:
            movie.in_dv_collection = False
    elif collection_type == "p7":
        success = await manager.remove_from_p7_collection(rating_key, movie.title)
        if success:
            movie.in_p7_collection = False
    elif collection_type == "atmos":
        success = await manager.remove_from_atmos_collection(rating_key, movie.title)
        if success:
            movie.in_atmos_collection = False
    else:
        raise HTTPException(status_code=400, detail="Invalid collection type")

    if not success:
        raise HTTPException(status_code=500, detail="Failed to remove from collection")

    # Record change
    change = CollectionChange(
        collection_name=f"{collection_type.upper()} Collection",
        collection_type=collection_type,
        movie_rating_key=rating_key,
        movie_title=movie.title,
        movie_year=movie.year,
        action="removed",
        reason="Manual removal via API",
        triggered_by="api",
    )
    db.add(change)

    await db.commit()

    return {"success": True, "message": f"Removed from {collection_type} collection"}


@router.get("/changes/history", response_model=list[dict[str, Any]])
async def get_collection_changes(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """
    Get recent collection change history

    Returns audit trail of collection modifications.
    """
    result = await db.execute(
        select(CollectionChange)
        .order_by(CollectionChange.created_at.desc())
        .limit(limit)
    )
    changes = result.scalars().all()

    return [
        {
            "id": change.id,
            "collection_name": change.collection_name,
            "collection_type": change.collection_type,
            "movie_rating_key": change.movie_rating_key,
            "movie_title": change.movie_title,
            "movie_year": change.movie_year,
            "action": change.action,
            "reason": change.reason,
            "triggered_by": change.triggered_by,
            "created_at": change.created_at,
        }
        for change in changes
    ]

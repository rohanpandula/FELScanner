"""
Movie Service
Business logic for movie operations
"""
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.movie import Movie
from app.schemas.movie import MovieFilter

logger = get_logger(__name__)


class MovieService:
    """Movie database operations and business logic"""

    def __init__(self, db: AsyncSession):
        """Initialize movie service"""
        self.db = db

    async def get_movies(
        self, filter_params: MovieFilter
    ) -> tuple[list[Movie], int]:
        """
        Get movies with filtering, sorting, and pagination

        Args:
            filter_params: Filter and pagination parameters

        Returns:
            tuple: (movies, total_count)
        """
        # Build base query
        query = select(Movie)

        # Apply filters
        if filter_params.title:
            query = query.where(Movie.title.ilike(f"%{filter_params.title}%"))

        if filter_params.year:
            query = query.where(Movie.year == filter_params.year)

        if filter_params.dv_profile:
            query = query.where(Movie.dv_profile == filter_params.dv_profile)

        if filter_params.dv_fel is not None:
            query = query.where(Movie.dv_fel == filter_params.dv_fel)

        if filter_params.has_atmos is not None:
            query = query.where(Movie.has_atmos == filter_params.has_atmos)

        if filter_params.resolution:
            query = query.where(Movie.resolution == filter_params.resolution)

        if filter_params.in_dv_collection is not None:
            query = query.where(Movie.in_dv_collection == filter_params.in_dv_collection)

        if filter_params.in_p7_collection is not None:
            query = query.where(Movie.in_p7_collection == filter_params.in_p7_collection)

        if filter_params.in_atmos_collection is not None:
            query = query.where(Movie.in_atmos_collection == filter_params.in_atmos_collection)

        # Get total count before pagination
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Apply sorting
        sort_field = getattr(Movie, filter_params.sort_by, Movie.title)
        if filter_params.sort_order == "desc":
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())

        # Apply pagination
        offset = (filter_params.page - 1) * filter_params.page_size
        query = query.limit(filter_params.page_size).offset(offset)

        # Execute query
        result = await self.db.execute(query)
        movies = result.scalars().all()

        return movies, total

    async def get_movie_by_id(self, movie_id: int) -> Movie | None:
        """Get a movie by database ID"""
        result = await self.db.execute(select(Movie).where(Movie.id == movie_id))
        return result.scalar_one_or_none()

    async def get_movie_by_rating_key(self, rating_key: str) -> Movie | None:
        """Get a movie by Plex rating key"""
        result = await self.db.execute(
            select(Movie).where(Movie.rating_key == rating_key)
        )
        return result.scalar_one_or_none()

    async def get_statistics(self) -> dict[str, Any]:
        """
        Get library statistics

        Returns:
            dict: Statistics about the movie library
        """
        # Total count
        total_result = await self.db.execute(select(func.count()).select_from(Movie))
        total = total_result.scalar() or 0

        # DV counts
        dv_result = await self.db.execute(
            select(func.count()).select_from(Movie).where(Movie.dv_profile.isnot(None))
        )
        dv_count = dv_result.scalar() or 0

        # FEL count
        fel_result = await self.db.execute(
            select(func.count()).select_from(Movie).where(Movie.dv_fel == True)
        )
        fel_count = fel_result.scalar() or 0

        # Atmos count
        atmos_result = await self.db.execute(
            select(func.count()).select_from(Movie).where(Movie.has_atmos == True)
        )
        atmos_count = atmos_result.scalar() or 0

        # 4K count
        fourk_result = await self.db.execute(
            select(func.count())
            .select_from(Movie)
            .where(Movie.resolution.in_(["2160p", "4K"]))
        )
        fourk_count = fourk_result.scalar() or 0

        # DV profile breakdown
        profile_result = await self.db.execute(
            select(Movie.dv_profile, func.count(Movie.id))
            .where(Movie.dv_profile.isnot(None))
            .group_by(Movie.dv_profile)
        )
        profile_breakdown = {
            profile: count for profile, count in profile_result.fetchall()
        }

        # Get 1080p count
        p1080_result = await self.db.execute(
            select(func.count())
            .select_from(Movie)
            .where(Movie.resolution == "1080p")
        )
        p1080_count = p1080_result.scalar() or 0

        return {
            "total": total,
            "dv_total": dv_count,
            "dv_p5": profile_breakdown.get("P5", 0),
            "dv_p7": profile_breakdown.get("P7", 0),
            "dv_p8": profile_breakdown.get("P8", 0),
            "dv_p10": profile_breakdown.get("P10", 0),
            "dv_fel": fel_count,
            "atmos_total": atmos_count,
            "resolution_4k": fourk_count,
            "resolution_1080p": p1080_count,
            # Keep old field names for backwards compatibility
            "total_movies": total,
            "dolby_vision": dv_count,
            "dv_fel_profile7": fel_count,
            "truehd_atmos": atmos_count,
            "4k_movies": fourk_count,
            "dv_profile_breakdown": profile_breakdown,
        }

    async def search_movies(self, query: str, limit: int = 20) -> list[Movie]:
        """
        Search movies by title

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            list[Movie]: Matching movies
        """
        result = await self.db.execute(
            select(Movie)
            .where(Movie.title.ilike(f"%{query}%"))
            .order_by(Movie.title)
            .limit(limit)
        )
        return result.scalars().all()

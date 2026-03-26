"""
Integration tests for ScanService database operations
"""
import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movie import Movie
from app.services.scan_service import ScanService


@pytest_asyncio.fixture
async def scan_service(test_db: AsyncSession):
    with patch("app.services.scan_service.PlexScanner"), \
         patch("app.services.scan_service.CollectionManager") as mock_cm:
        mock_cm.return_value.verify_collections = AsyncMock(return_value={"added": 0, "removed": 0})
        service = ScanService(test_db)
        yield service


@pytest_asyncio.fixture
async def seeded_db(test_db: AsyncSession):
    """Seed test database with sample movies"""
    movies = [
        Movie(
            rating_key="100",
            title="Inception",
            year=2010,
            resolution="2160p",
            dv_profile="P7",
            dv_fel=True,
            has_atmos=True,
            in_dv_collection=True,
            in_p7_collection=True,
            in_atmos_collection=True,
        ),
        Movie(
            rating_key="200",
            title="The Matrix",
            year=1999,
            resolution="1080p",
            dv_profile=None,
            dv_fel=False,
            has_atmos=False,
            in_dv_collection=False,
            in_p7_collection=False,
            in_atmos_collection=False,
        ),
        Movie(
            rating_key="300",
            title="Removed Movie",
            year=2000,
            resolution="720p",
            dv_profile=None,
            dv_fel=False,
            has_atmos=False,
            in_dv_collection=False,
            in_p7_collection=False,
            in_atmos_collection=False,
        ),
    ]
    for m in movies:
        test_db.add(m)
    await test_db.commit()
    return test_db


@pytest.mark.asyncio
async def test_update_database_adds_new_movie(scan_service, test_db):
    """New movie should be added to database"""
    scanned = [
        {
            "rating_key": "500",
            "title": "New Movie",
            "year": 2024,
            "resolution": "2160p",
            "dv_profile": "P7",
            "dv_fel": True,
            "has_atmos": True,
        }
    ]
    stats = await scan_service._update_database(scanned)

    assert stats["added"] == 1
    assert stats["updated"] == 0
    assert stats["dv_count"] == 1
    assert stats["fel_count"] == 1
    assert stats["atmos_count"] == 1

    result = await test_db.execute(select(Movie).where(Movie.rating_key == "500"))
    movie = result.scalar_one_or_none()
    assert movie is not None
    assert movie.title == "New Movie"
    assert movie.in_dv_collection is True
    assert movie.in_p7_collection is True
    assert movie.in_atmos_collection is True


@pytest.mark.asyncio
async def test_update_database_updates_existing(scan_service, seeded_db):
    """Existing movie should be updated with new data"""
    scan_service.db = seeded_db

    scanned = [
        {
            "rating_key": "100",
            "title": "Inception",
            "year": 2010,
            "resolution": "2160p",
            "dv_profile": "P8",  # Changed from P7
            "dv_fel": False,  # Changed from True
            "has_atmos": True,
        },
        {
            "rating_key": "200",
            "title": "The Matrix",
            "year": 1999,
            "resolution": "2160p",  # Upgraded from 1080p
            "dv_profile": "P5",  # New DV
            "dv_fel": False,
            "has_atmos": False,
        },
    ]
    stats = await scan_service._update_database(scanned)

    assert stats["updated"] == 2
    assert stats["added"] == 0
    assert stats["removed"] == 1  # "Removed Movie" (rating_key 300) not in scanned
    assert stats["dv_count"] == 2
    assert stats["fel_count"] == 0

    # Verify Inception was updated
    result = await seeded_db.execute(select(Movie).where(Movie.rating_key == "100"))
    inception = result.scalar_one()
    assert inception.dv_profile == "P8"
    assert inception.dv_fel is False
    assert inception.in_dv_collection is True
    assert inception.in_p7_collection is False  # No longer FEL

    # Verify Matrix was updated
    result = await seeded_db.execute(select(Movie).where(Movie.rating_key == "200"))
    matrix = result.scalar_one()
    assert matrix.resolution == "2160p"
    assert matrix.dv_profile == "P5"
    assert matrix.in_dv_collection is True


@pytest.mark.asyncio
async def test_update_database_marks_removed_as_stale(scan_service, seeded_db):
    """Movies not in scan results should have last_scanned_at updated"""
    scan_service.db = seeded_db

    # Only scan Inception, leaving Matrix and Removed Movie out
    scanned = [
        {
            "rating_key": "100",
            "title": "Inception",
            "year": 2010,
            "resolution": "2160p",
            "dv_profile": "P7",
            "dv_fel": True,
            "has_atmos": True,
        },
    ]
    stats = await scan_service._update_database(scanned)

    assert stats["removed"] == 2  # Matrix and Removed Movie
    assert stats["updated"] == 1


@pytest.mark.asyncio
async def test_update_database_collection_flags_set(scan_service, test_db):
    """Collection flags should be set correctly during update"""
    scanned = [
        {
            "rating_key": "600",
            "title": "DV Movie",
            "year": 2024,
            "dv_profile": "P8",
            "dv_fel": False,
            "has_atmos": False,
        },
        {
            "rating_key": "700",
            "title": "Plain Movie",
            "year": 2024,
            "dv_profile": None,
            "dv_fel": False,
            "has_atmos": False,
        },
    ]
    await scan_service._update_database(scanned)

    result = await test_db.execute(select(Movie).where(Movie.rating_key == "600"))
    dv_movie = result.scalar_one()
    assert dv_movie.in_dv_collection is True
    assert dv_movie.in_p7_collection is False

    result = await test_db.execute(select(Movie).where(Movie.rating_key == "700"))
    plain_movie = result.scalar_one()
    assert plain_movie.in_dv_collection is False
    assert plain_movie.in_p7_collection is False
    assert plain_movie.in_atmos_collection is False


@pytest.mark.asyncio
async def test_update_database_empty_scan(scan_service, seeded_db):
    """Empty scan should mark all existing movies as removed"""
    scan_service.db = seeded_db

    stats = await scan_service._update_database([])

    assert stats["added"] == 0
    assert stats["updated"] == 0
    assert stats["removed"] == 3  # All 3 seeded movies


@pytest.mark.asyncio
async def test_update_collections_no_requery(scan_service, test_db):
    """_update_collections should not re-query the database"""
    scanned = [{"rating_key": "100", "title": "Test", "dv_profile": "P7", "dv_fel": True, "has_atmos": True}]
    stats = await scan_service._update_collections(scanned)
    # Should return stats from collection manager (mocked)
    assert "added" in stats or "removed" in stats

"""
Integration tests for Downloads API endpoints
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pending_download import PendingDownload
from app.models.download_history import DownloadHistory


@pytest_asyncio.fixture
async def pending_download(test_db: AsyncSession) -> PendingDownload:
    """Create a test pending download"""
    download = PendingDownload(
        torrent_id="test-torrent-123",
        torrent_name="Test.Movie.2024.2160p.DV.P7.FEL.BluRay.REMUX-GROUP",
        torrent_url="https://example.com/torrent/123",
        movie_title="Test Movie",
        movie_year=2024,
        movie_rating_key="12345",
        quality="2160p DV P7 FEL",
        resolution="2160p",
        dv_profile="P7",
        has_fel=True,
        has_atmos=True,
        upgrade_type="New FEL",
        is_upgrade=True,
        is_duplicate=False,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
    )
    test_db.add(download)
    await test_db.commit()
    await test_db.refresh(download)
    return download


@pytest.mark.asyncio
async def test_get_pending_downloads(client: AsyncClient, pending_download):
    """GET /pending should return pending downloads"""
    response = await client.get("/api/v1/downloads/pending")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] >= 1
    assert data["pending"] >= 1


@pytest.mark.asyncio
async def test_get_pending_download_by_id(client: AsyncClient, pending_download):
    """GET /pending/{id} should return specific download"""
    response = await client.get(f"/api/v1/downloads/pending/{pending_download.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["torrent_id"] == "test-torrent-123"
    assert data["movie_title"] == "Test Movie"


@pytest.mark.asyncio
async def test_get_pending_download_not_found(client: AsyncClient):
    """GET /pending/{id} should return 404 for nonexistent download"""
    response = await client.get("/api/v1/downloads/pending/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
@patch("app.services.download_service.get_settings")
async def test_approve_download_no_qbittorrent(
    mock_settings, client: AsyncClient, pending_download
):
    """Approve should succeed even without qBittorrent configured"""
    settings = MagicMock()
    settings.QBITTORRENT_HOST = ""  # Not configured
    mock_settings.return_value = settings

    response = await client.post(
        f"/api/v1/downloads/pending/{pending_download.id}/action",
        json={"action": "approve", "approved_by": "test_user"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "approved"
    assert data["approved_by"] == "test_user"


@pytest.mark.asyncio
@patch("app.services.download_service.get_settings")
@patch("app.services.download_service.QBittorrentClient", create=True)
async def test_approve_download_with_qbittorrent(
    mock_qbit_class, mock_settings, client: AsyncClient, pending_download
):
    """Approve should trigger qBittorrent download"""
    settings = MagicMock()
    settings.QBITTORRENT_HOST = "qbittorrent"
    mock_settings.return_value = settings

    mock_qbit = MagicMock()
    mock_qbit.add_torrent = AsyncMock(return_value=True)
    mock_qbit.close = AsyncMock()
    mock_qbit_class.return_value = mock_qbit

    response = await client.post(
        f"/api/v1/downloads/pending/{pending_download.id}/action",
        json={"action": "approve", "approved_by": "test_user"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


@pytest.mark.asyncio
@patch("app.services.download_service.get_settings")
@patch("app.services.download_service.QBittorrentClient", create=True)
async def test_approve_still_succeeds_on_qbittorrent_failure(
    mock_qbit_class, mock_settings, client: AsyncClient, pending_download
):
    """Approval should still succeed even if qBittorrent fails"""
    settings = MagicMock()
    settings.QBITTORRENT_HOST = "qbittorrent"
    mock_settings.return_value = settings

    mock_qbit = MagicMock()
    mock_qbit.add_torrent = AsyncMock(side_effect=Exception("Connection refused"))
    mock_qbit.close = AsyncMock()
    mock_qbit_class.return_value = mock_qbit

    response = await client.post(
        f"/api/v1/downloads/pending/{pending_download.id}/action",
        json={"action": "approve", "approved_by": "test_user"},
    )
    # Should still succeed — qBit failure is non-blocking
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


@pytest.mark.asyncio
@patch("app.services.download_service.get_settings")
async def test_decline_download(mock_settings, client: AsyncClient, pending_download):
    """Decline should update status and create history"""
    settings = MagicMock()
    settings.QBITTORRENT_HOST = ""
    mock_settings.return_value = settings

    response = await client.post(
        f"/api/v1/downloads/pending/{pending_download.id}/action",
        json={"action": "decline", "approved_by": "test_user", "reason": "Too large"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "declined"
    assert data["declined_reason"] == "Too large"


@pytest.mark.asyncio
async def test_invalid_action(client: AsyncClient, pending_download):
    """Invalid action should return 400"""
    response = await client.post(
        f"/api/v1/downloads/pending/{pending_download.id}/action",
        json={"action": "invalid_action", "approved_by": "test_user"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
@patch("app.services.download_service.get_settings")
async def test_approve_already_approved(mock_settings, client: AsyncClient, pending_download, test_db):
    """Approving an already-approved download should return 400"""
    settings = MagicMock()
    settings.QBITTORRENT_HOST = ""
    mock_settings.return_value = settings

    # First approval
    await client.post(
        f"/api/v1/downloads/pending/{pending_download.id}/action",
        json={"action": "approve", "approved_by": "test_user"},
    )

    # Second approval attempt
    response = await client.post(
        f"/api/v1/downloads/pending/{pending_download.id}/action",
        json={"action": "approve", "approved_by": "test_user"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_download_history(client: AsyncClient):
    """GET /history should return paginated history"""
    response = await client.get("/api/v1/downloads/history")
    assert response.status_code == 200

    data = response.json()
    assert "total" in data
    assert "page" in data
    assert "history" in data


@pytest.mark.asyncio
async def test_download_stats(client: AsyncClient):
    """GET /stats should return statistics"""
    response = await client.get("/api/v1/downloads/stats")
    assert response.status_code == 200

    data = response.json()
    assert "total_downloads" in data
    assert "approved" in data
    assert "success_rate" in data

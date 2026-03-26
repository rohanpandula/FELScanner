"""
Integration tests for IPT Scanner API endpoints

Tests the FastAPI endpoints with mocked IPT scraper service
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
import httpx as httpx_module


@pytest.mark.asyncio
async def test_get_cached_torrents_success(client: AsyncClient):
    """Test GET /api/v1/ipt/cache endpoint with torrents"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "torrents": [
            {
                "id": "12345",
                "title": "Test.Movie.2024.DV.2160p",
                "size": "50 GB",
                "url": "https://example.com/1"
            },
            {
                "id": "67890",
                "title": "Another.Movie.2024.P7.FEL.2160p",
                "size": "45 GB",
                "url": "https://example.com/2"
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        response = await client.get("/api/v1/ipt/cache")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == "12345"
        assert data[1]["title"] == "Another.Movie.2024.P7.FEL.2160p"


@pytest.mark.asyncio
async def test_get_cached_torrents_empty(client: AsyncClient):
    """Test GET /api/v1/ipt/cache with empty cache"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"torrents": []}
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        response = await client.get("/api/v1/ipt/cache")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


@pytest.mark.asyncio
async def test_get_cached_torrents_error(client: AsyncClient):
    """Test GET /api/v1/ipt/cache when scraper is unreachable"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx_module.ConnectError("Connection refused")
        )

        response = await client.get("/api/v1/ipt/cache")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to retrieve cache" in data["detail"]


@pytest.mark.asyncio
async def test_get_scan_results_success(client: AsyncClient):
    """Test GET /api/v1/ipt/results endpoint"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "timestamp": "2026-01-05T08:00:00.000Z",
        "results": {
            "total": 5,
            "torrents": [
                {"title": "Movie.DV", "size": "40 GB"}
            ]
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        response = await client.get("/api/v1/ipt/results")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["results"]["total"] == 5
        assert len(data["results"]["torrents"]) == 1


@pytest.mark.asyncio
async def test_get_scan_results_error(client: AsyncClient):
    """Test GET /api/v1/ipt/results when scraper is unreachable"""
    # This should return empty results, not raise error
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx_module.ConnectError("Connection refused")
        )

        response = await client.get("/api/v1/ipt/results")

        # Service returns empty results on error, so 200 is expected
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["results"]["total"] == 0


@pytest.mark.asyncio
async def test_trigger_scan_success(client: AsyncClient):
    """Test POST /api/v1/ipt/scan endpoint"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "timestamp": "2026-01-05T08:00:00.000Z",
        "results": {
            "total": 10,
            "new": 3,
            "torrents": [
                {
                    "title": "New.Movie.2024.DV.2160p",
                    "size": "50 GB",
                    "url": "https://example.com/1",
                    "isNew": True
                },
                {
                    "title": "Another.Movie.2024.P7.FEL.2160p",
                    "size": "45 GB",
                    "url": "https://example.com/2",
                    "isNew": True
                },
                {
                    "title": "Known.Movie.2024.DV.2160p",
                    "size": "48 GB",
                    "url": "https://example.com/3",
                    "isNew": False
                }
            ]
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        response = await client.post("/api/v1/ipt/scan")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["results"]["total"] == 10
        assert data["results"]["new"] == 3
        assert len(data["results"]["torrents"]) == 3


@pytest.mark.asyncio
async def test_trigger_scan_error(client: AsyncClient):
    """Test POST /api/v1/ipt/scan when scraper is unreachable"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx_module.ConnectError("Connection refused")
        )

        response = await client.post("/api/v1/ipt/scan")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to trigger scan" in data["detail"]


@pytest.mark.asyncio
async def test_trigger_scan_timeout(client: AsyncClient):
    """Test POST /api/v1/ipt/scan with timeout"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx_module.TimeoutException("Request timeout")
        )

        response = await client.post("/api/v1/ipt/scan")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to trigger scan" in data["detail"]


@pytest.mark.asyncio
async def test_clear_cache_success(client: AsyncClient):
    """Test POST /api/v1/ipt/cache/clear endpoint"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": "Cache cleared successfully"}
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.delete = AsyncMock(return_value=mock_response)

        response = await client.post("/api/v1/ipt/cache/clear")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "cleared" in data["message"].lower()


@pytest.mark.asyncio
async def test_clear_cache_error(client: AsyncClient):
    """Test POST /api/v1/ipt/cache/clear when scraper is unreachable"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.delete = AsyncMock(
            side_effect=httpx_module.ConnectError("Connection refused")
        )

        response = await client.post("/api/v1/ipt/cache/clear")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to clear cache" in data["detail"]


@pytest.mark.asyncio
async def test_check_health_healthy(client: AsyncClient):
    """Test GET /api/v1/ipt/health when scraper is healthy"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "ok",
        "version": "2.0.0",
        "uptime": 12345
    }
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        response = await client.get("/api/v1/ipt/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "2.0.0" in data["message"]
        assert data["uptime"] == 12345


@pytest.mark.asyncio
async def test_check_health_unhealthy(client: AsyncClient):
    """Test GET /api/v1/ipt/health when scraper is unreachable"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx_module.ConnectError("Connection refused")
        )

        response = await client.get("/api/v1/ipt/health")

        # Health check returns 200 with unhealthy status
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "unreachable" in data["message"].lower()


@pytest.mark.asyncio
async def test_ipt_endpoints_require_no_auth(client: AsyncClient):
    """Test that IPT endpoints don't require authentication"""
    # All endpoints should be accessible without auth tokens
    mock_response = MagicMock()
    mock_response.json.return_value = {"torrents": []}
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        response = await client.get("/api/v1/ipt/cache")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_scan_endpoint_returns_new_count(client: AsyncClient):
    """Test that scan endpoint properly returns new torrent count"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "timestamp": "2026-01-05T08:00:00.000Z",
        "results": {
            "total": 5,
            "new": 2,
            "torrents": []
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        response = await client.post("/api/v1/ipt/scan")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "new" in data["results"]
        assert data["results"]["new"] == 2

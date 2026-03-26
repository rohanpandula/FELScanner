"""
Unit tests for IPT Scanner Service

Tests IPTService methods with mocked httpx calls
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.ipt_service import IPTService


@pytest.fixture
def ipt_service():
    """Create IPTService instance"""
    return IPTService()


@pytest.mark.asyncio
async def test_trigger_scan_success(ipt_service):
    """Test successful IPT scan trigger"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "timestamp": "2026-01-05T08:00:00.000Z",
        "results": {
            "total": 5,
            "new": 2,
            "torrents": [
                {
                    "title": "Movie.2024.DV.2160p",
                    "size": "50 GB",
                    "url": "https://example.com/1"
                },
                {
                    "title": "Another.Movie.2024.P7.FEL.2160p",
                    "size": "45 GB",
                    "url": "https://example.com/2"
                }
            ]
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        result = await ipt_service.trigger_scan()

        assert result["success"] is True
        assert result["results"]["total"] == 5
        assert result["results"]["new"] == 2
        assert len(result["results"]["torrents"]) == 2
        assert result["results"]["torrents"][0]["title"] == "Movie.2024.DV.2160p"


@pytest.mark.asyncio
async def test_trigger_scan_failure(ipt_service):
    """Test IPT scan trigger when scraper is unreachable"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(httpx.HTTPError):
            await ipt_service.trigger_scan()


@pytest.mark.asyncio
async def test_trigger_scan_timeout(ipt_service):
    """Test IPT scan trigger with timeout"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.TimeoutException("Request timeout")
        )

        with pytest.raises(httpx.HTTPError):
            await ipt_service.trigger_scan()


@pytest.mark.asyncio
async def test_get_latest_results_success(ipt_service):
    """Test getting latest scan results"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "timestamp": "2026-01-05T08:00:00.000Z",
        "results": {
            "total": 3,
            "torrents": [
                {"title": "Test.Movie.DV", "size": "40 GB"}
            ]
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await ipt_service.get_latest_results()

        assert result["success"] is True
        assert result["results"]["total"] == 3
        assert len(result["results"]["torrents"]) == 1


@pytest.mark.asyncio
async def test_get_latest_results_failure(ipt_service):
    """Test getting latest results when scraper is down"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        result = await ipt_service.get_latest_results()

        # Should return empty results on error, not raise
        assert result["success"] is False
        assert result["timestamp"] is None
        assert result["results"]["total"] == 0
        assert result["results"]["torrents"] == []


@pytest.mark.asyncio
async def test_get_known_torrents_success(ipt_service):
    """Test getting known torrents from cache"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "torrents": [
            {"id": "12345", "title": "Cached.Movie.DV"},
            {"id": "67890", "title": "Another.Cached.Movie.P7"}
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await ipt_service.get_known_torrents()

        assert len(result) == 2
        assert result[0]["id"] == "12345"
        assert result[1]["title"] == "Another.Cached.Movie.P7"


@pytest.mark.asyncio
async def test_get_known_torrents_empty(ipt_service):
    """Test getting known torrents when cache is empty"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"torrents": []}
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await ipt_service.get_known_torrents()

        assert result == []


@pytest.mark.asyncio
async def test_get_known_torrents_failure(ipt_service):
    """Test getting known torrents when scraper is unreachable"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        result = await ipt_service.get_known_torrents()

        # Should return empty list on error, not raise
        assert result == []


@pytest.mark.asyncio
async def test_clear_cache_success(ipt_service):
    """Test clearing known torrents cache"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": "Cache cleared successfully"}
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.delete = AsyncMock(return_value=mock_response)

        result = await ipt_service.clear_cache()

        assert "message" in result
        assert "cleared" in result["message"].lower()


@pytest.mark.asyncio
async def test_clear_cache_failure(ipt_service):
    """Test clearing cache when scraper is unreachable"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.delete = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(httpx.HTTPError):
            await ipt_service.clear_cache()


@pytest.mark.asyncio
async def test_check_health_success(ipt_service):
    """Test health check when scraper is healthy"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "ok",
        "version": "2.0.0",
        "uptime": 12345
    }
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await ipt_service.check_health()

        assert result["status"] == "healthy"
        assert "2.0.0" in result["message"]
        assert result["uptime"] == 12345


@pytest.mark.asyncio
async def test_check_health_failure(ipt_service):
    """Test health check when scraper is unreachable"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        result = await ipt_service.check_health()

        assert result["status"] == "unhealthy"
        assert "unreachable" in result["message"].lower()


@pytest.mark.asyncio
async def test_service_initialization(ipt_service):
    """Test IPTService initialization with settings"""
    assert ipt_service.scraper_url is not None
    assert ipt_service.timeout == 60.0


@pytest.mark.asyncio
async def test_trigger_scan_uses_correct_timeout(ipt_service):
    """Test that trigger_scan uses appropriate timeout for long operations"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "timestamp": "2026-01-05T08:00:00.000Z",
        "results": {"total": 0, "torrents": []}
    }
    mock_response.raise_for_status = MagicMock()

    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = MagicMock()
        mock_instance.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client.return_value = mock_instance

        await ipt_service.trigger_scan()

        # Verify AsyncClient was created with 60s timeout
        mock_client.assert_called_once_with(timeout=60.0)

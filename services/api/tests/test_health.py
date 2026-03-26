"""
Test health check endpoints
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test basic health check endpoint"""
    response = await client.get("/health")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "app" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_readiness_check(client: AsyncClient):
    """Test readiness check endpoint"""
    response = await client.get("/health/ready")

    # May be 200 or 503 depending on dependencies
    assert response.status_code in [200, 503]

    data = response.json()
    assert "status" in data
    assert "checks" in data


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root API endpoint"""
    response = await client.get("/")

    assert response.status_code == 200

    data = response.json()
    assert "app" in data
    assert "version" in data
    assert "docs" in data
    assert "metrics" in data

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check_api():
    """
    Test the fundamental backend availability via standard HTTP GET.
    This replaces the obsolete 'test_basic_health_check' dummy test
    with an actual client route regression test.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        
    assert response.status_code == 200
    res_data = response.json()
    assert res_data.get("success") is True
    data = res_data.get("data", {})
    assert data.get("status") in ["ok", "healthy", "error"]

import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_register_user():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "testpassword",
                "full_name": "Test User"
            }
        )
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_login():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/auth/token",
            data={
                "username": "test@example.com",
                "password": "testpassword"
            }
        )
    assert response.status_code == 200
    assert "access_token" in response.json() 
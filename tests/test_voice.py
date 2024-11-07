import pytest
from httpx import AsyncClient
from app.main import app
import io

@pytest.mark.asyncio
async def test_create_voice():
    # Create a mock audio file
    audio_data = io.BytesIO(b"mock audio data")
    audio_data.name = "test.wav"
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/voice/voices/",
            data={
                "name": "Test Voice",
                "description": "Test Description"
            },
            files={"file": ("test.wav", audio_data, "audio/wav")}
        )
    assert response.status_code == 200
    assert response.json()["name"] == "Test Voice"

@pytest.mark.asyncio
async def test_create_cloning_job():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/voice/clone/",
            json={
                "voice_id": 1,
                "input_text": "Hello, this is a test."
            }
        )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"

@pytest.mark.asyncio
async def test_list_voices():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/voice/voices/")
    assert response.status_code == 200
    assert isinstance(response.json(), list) 
import pytest
from httpx import AsyncClient
from app.main import app
import io

@pytest.mark.asyncio
async def test_create_translation_job():
    # Create a mock audio file
    audio_data = io.BytesIO(b"mock audio data")
    audio_data.name = "test.wav"
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/translation/translate/",
            data={
                "target_language": "es",
                "source_language": "en"
            },
            files={"file": ("test.wav", audio_data, "audio/wav")}
        )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"

@pytest.mark.asyncio
async def test_list_translations():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/translation/translations/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_get_translation():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/translation/translations/1")
    assert response.status_code == 200 or response.status_code == 404 
from fastapi import APIRouter
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

router = APIRouter()

API_DESCRIPTION = """
# Audio Processing API

This API provides voice cloning and audio translation services with high-performance processing capabilities.

## Authentication

All endpoints require JWT authentication. To get started:
1. Register a new account at `/auth/register`
2. Get your access token from `/auth/token`
3. Include the token in all requests: `Authorization: Bearer <your_token>`

## Rate Limiting

- 100 requests per minute per IP address
- Larger files (>50MB) count as multiple requests

## Voice Cloning

### Process:
1. Upload a voice sample (`/voice/voices/`)
2. Create a cloning job (`/voice/clone/`)
3. Check job status (`/voice/clone/{job_id}`)
4. Download generated audio when complete

### Supported Formats:
- WAV (preferred)
- MP3
- OGG

### Best Practices:
- Use high-quality audio samples (16kHz+)
- Keep samples between 10-30 seconds
- Avoid background noise
- Use clear speech samples

## Audio Translation

### Features:
- Automatic language detection
- Multiple target languages
- High accuracy transcription
- Audio-to-audio translation

### Supported Languages:
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Dutch (nl)
- Russian (ru)
- Chinese (zh)
- Japanese (ja)
- Korean (ko)

### Performance Tips:
- Use WAV format for best results
- Keep files under 100MB for optimal processing
- Consider chunking large files
"""

VOICE_EXAMPLES = {
    "create_voice": {
        "summary": "Create a new voice profile",
        "description": "Upload a voice sample to create a new voice profile for cloning",
        "request": {
            "content": {
                "multipart/form-data": {
                    "example": {
                        "name": "John's Voice",
                        "description": "Male voice sample for testing",
                        "file": "binary_file_content"
                    }
                }
            }
        },
        "responses": {
            "200": {
                "description": "Voice profile created successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "name": "John's Voice",
                            "description": "Male voice sample for testing",
                            "file_path": "voices/uuid/sample.wav",
                            "created_at": "2024-01-01T12:00:00Z"
                        }
                    }
                }
            }
        }
    }
}

TRANSLATION_EXAMPLES = {
    "create_translation": {
        "summary": "Create a new translation job",
        "description": "Upload an audio file for translation to target language",
        "request": {
            "content": {
                "multipart/form-data": {
                    "example": {
                        "target_language": "es",
                        "source_language": "en",
                        "file": "binary_file_content"
                    }
                }
            }
        },
        "responses": {
            "200": {
                "description": "Translation job created successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "status": "pending",
                            "source_language": "en",
                            "target_language": "es",
                            "input_path": "translations/inputs/uuid/audio.wav",
                            "created_at": "2024-01-01T12:00:00Z"
                        }
                    }
                }
            }
        }
    }
}

@router.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/api/v1/openapi.json",
        title="Audio Processing API - Documentation",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Audio Processing API",
        version="1.0.0",
        description=API_DESCRIPTION,
        routes=app.routes,
    )
    
    # Add authentication scheme
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    
    # Add examples
    paths = openapi_schema["paths"]
    if "/api/v1/voice/voices/" in paths:
        paths["/api/v1/voice/voices/"]["post"].update(VOICE_EXAMPLES["create_voice"])
    if "/api/v1/translation/translate/" in paths:
        paths["/api/v1/translation/translate/"]["post"].update(TRANSLATION_EXAMPLES["create_translation"])
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Update main app
app.openapi = custom_openapi 
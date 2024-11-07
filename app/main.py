from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.v1 import voice, translation, auth
from app.core.middleware import rate_limit_middleware
from app.core.logging import setup_logging
from app.core.metrics import MetricsMiddleware
from prometheus_client import make_asgi_app
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.errors import AudioProcessingError
from pathlib import Path

settings = get_settings()
logger = setup_logging()

def verify_models():
    """Verify all required model files exist"""
    # Check XTTS files
    xtts_files = {
        "model": settings.XTTS_MODEL_PATH,
        "config": settings.XTTS_CONFIG_PATH,
        "vocab": settings.XTTS_VOCAB_PATH,
        "speakers": settings.XTTS_SPEAKERS_PATH
    }
    
    # Check Whisper files
    whisper_files = {
        "model": settings.WHISPER_MODEL_PATH,
        "config": settings.WHISPER_CONFIG_PATH,
        "vocab": str(Path(settings.WHISPER_MODEL_PATH).parent / "vocabulary.json")
    }
    
    missing_files = []
    for name, path in {**xtts_files, **whisper_files}.items():
        if not Path(path).exists():
            missing_files.append(f"{name}: {path}")
    
    if missing_files:
        raise RuntimeError(f"Missing model files:\n" + "\n".join(missing_files))

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# Add metrics middleware
app.middleware("http")(MetricsMiddleware())

# Mount metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(voice.router, prefix=f"{settings.API_V1_STR}/voice", tags=["voice"])
app.include_router(translation.router, prefix=f"{settings.API_V1_STR}/translation", tags=["translation"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    verify_models()
    logger.info("Starting up application...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down application...")

@app.exception_handler(AudioProcessingError)
async def audio_processing_error_handler(request, exc: AudioProcessingError):
    return JSONResponse(
        status_code=400,
        content=exc.to_dict()
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "Internal server error"
        }
    ) 
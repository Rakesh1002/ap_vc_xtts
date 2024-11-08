from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import voice, translation, auth, speaker, denoiser
from app.core.config import get_settings
from app.core.middleware import metrics_middleware, rate_limit_middleware
from prometheus_client import make_asgi_app
import logging
from app.core.service_registry import (
    get_diarization_service,
    get_extraction_service
)
from app.core.device import get_device_manager
import torch

# Initialize settings and logger
settings = get_settings()
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    debug=settings.DEBUG
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.middleware("http")(metrics_middleware)
app.middleware("http")(rate_limit_middleware)

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include API routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(voice.router, prefix=f"{settings.API_V1_STR}/voice", tags=["voice"])
app.include_router(translation.router, prefix=f"{settings.API_V1_STR}/translation", tags=["translation"])
app.include_router(speaker.router, prefix=f"{settings.API_V1_STR}/speaker", tags=["speaker"])
app.include_router(
    denoiser.router,
    prefix=f"{settings.API_V1_STR}/denoiser",
    tags=["denoiser"]
)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting up API server...")
    
    try:
        # Initialize device manager
        device_manager = get_device_manager()
        logger.info(f"Using device: {device_manager.device}")
        
        # Pre-initialize speaker services
        diarization_service = get_diarization_service()
        extraction_service = get_extraction_service()
        logger.info("Speaker analysis services initialized")
        
        # Initialize denoiser services
        from app.services.spectral_denoiser_service import SpectralDenoiserService
        
        spectral_service = SpectralDenoiserService()
        if spectral_service.initialized:
            logger.info("Spectral denoiser service initialized successfully")
        else:
            logger.warning("Spectral denoiser service initialization failed. Some features may be unavailable.")
        
        # Log GPU availability
        if device_manager.is_gpu_available:
            logger.info(f"GPU available: {torch.cuda.get_device_name(0)}")
            logger.info(f"GPU memory: {device_manager.get_memory_stats()}")
        else:
            logger.warning("No GPU available, using CPU")
            
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down API server...")
    try:
        # Clear GPU cache if available
        device_manager = get_device_manager()
        if device_manager.is_gpu_available:
            device_manager.clear_cache()
            logger.info("GPU cache cleared")
            
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import voice, translation, auth
from app.core.config import get_settings
from app.core.middleware import metrics_middleware, rate_limit_middleware
from prometheus_client import make_asgi_app
import logging

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

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting up API server...")
    # Add any startup initialization here

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down API server...")
    # Add any cleanup code here
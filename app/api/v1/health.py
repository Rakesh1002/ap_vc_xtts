from fastapi import APIRouter
import torch
from app.core.config import get_settings
from app.core.models import check_models_loaded

router = APIRouter()

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "gpu_available": torch.cuda.is_available(),
        "models_loaded": check_models_loaded()
    } 
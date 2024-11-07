from fastapi import APIRouter
import torch
from app.core.config import get_settings

router = APIRouter()

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": get_settings().VERSION,
        "gpu_available": torch.cuda.is_available(),
    } 
import torch
import logging
from typing import Dict, Any
import psutil
from app.core.config import get_settings
from app.core.metrics import RESOURCE_USAGE, GPU_METRICS

logger = logging.getLogger(__name__)
settings = get_settings()

class DeviceManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DeviceManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize device settings"""
        self.settings = get_settings()
        self._setup_device()
        self._setup_compute_type()

    def _setup_device(self):
        """Setup device and CUDA if available"""
        if torch.cuda.is_available():
            # Set memory growth
            for device in range(torch.cuda.device_count()):
                torch.cuda.set_per_process_memory_fraction(0.8, device)
            
            self.device = torch.device("cuda")
            self.is_gpu_available = True
            logger.info("Using CUDA device")
        else:
            self.device = torch.device("cpu")
            self.is_gpu_available = False
            logger.info("Using CPU device")

    def _setup_compute_type(self):
        """Setup compute type based on device capabilities"""
        if self.is_gpu_available:
            # Check if GPU supports mixed precision
            if torch.cuda.is_bf16_supported():
                self.compute_type = "bfloat16"
            else:
                self.compute_type = "float32"
        else:
            self.compute_type = "float32"
        
        logger.info(f"Using compute type: {self.compute_type}")

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current memory statistics"""
        stats = {
            'ram_used': psutil.virtual_memory().percent,
            'ram_available': psutil.virtual_memory().available / (1024 * 1024 * 1024)  # GB
        }
        
        if self.is_gpu_available:
            stats.update({
                'gpu_used': torch.cuda.memory_allocated() / (1024 * 1024 * 1024),  # GB
                'gpu_cached': torch.cuda.memory_reserved() / (1024 * 1024 * 1024)  # GB
            })
            
            # Update metrics
            GPU_METRICS.labels(device="cuda:0", metric="memory_used").set(stats['gpu_used'])
            GPU_METRICS.labels(device="cuda:0", metric="memory_cached").set(stats['gpu_cached'])
        
        # Update RAM metrics
        RESOURCE_USAGE.labels(resource="ram", type="used").set(stats['ram_used'])
        RESOURCE_USAGE.labels(resource="ram", type="available").set(stats['ram_available'])
        
        return stats

    def clear_cache(self):
        """Clear GPU cache if available"""
        if self.is_gpu_available:
            torch.cuda.empty_cache()
            logger.debug("Cleared GPU cache")

    def get_device(self) -> torch.device:
        """Get current device"""
        return self.device

    def get_compute_type(self) -> str:
        """Get current compute type"""
        return self.compute_type

def get_device_manager() -> DeviceManager:
    """Get singleton instance of DeviceManager"""
    return DeviceManager() 
"""Core optimization and resource management"""
from typing import Dict, Any
import psutil
import torch
from app.core.config import get_settings
from app.core.memory import memory_manager
from app.core.metrics import RESOURCE_USAGE
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

class ResourceOptimizer:
    def __init__(self):
        self.memory_manager = memory_manager
        self.settings = get_settings()
        self._init_gpu()

    def _init_gpu(self):
        """Initialize GPU settings"""
        if torch.cuda.is_available():
            # Set memory growth
            for device in range(torch.cuda.device_count()):
                torch.cuda.set_per_process_memory_fraction(0.8, device)
                
            # Optimize allocator
            torch.cuda.set_per_process_memory_fraction(0.8)
            torch.backends.cudnn.benchmark = True

    def optimize_for_inference(self):
        """Optimize system for inference"""
        # Clear memory
        self.memory_manager.cleanup()
        
        # Set process priority
        try:
            psutil.Process().nice(10)
        except Exception as e:
            logger.warning(f"Failed to set process priority: {e}")

    def get_resource_metrics(self) -> Dict[str, Any]:
        """Get current resource metrics"""
        metrics = {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
        }
        
        if torch.cuda.is_available():
            metrics.update({
                'gpu_memory_allocated': torch.cuda.memory_allocated(),
                'gpu_memory_cached': torch.cuda.memory_reserved(),
            })
            
        # Update Prometheus metrics
        RESOURCE_USAGE.labels(resource='cpu').set(metrics['cpu_percent'])
        RESOURCE_USAGE.labels(resource='memory').set(metrics['memory_percent'])
        
        return metrics

resource_optimizer = ResourceOptimizer()
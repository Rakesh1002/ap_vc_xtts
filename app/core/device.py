import torch
import psutil
import logging
from typing import Dict, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

class DeviceManager:
    def __init__(self):
        self.device = self._get_optimal_device()
        self.memory_stats: Dict[str, float] = {}
        
    def _get_optimal_device(self) -> torch.device:
        if torch.cuda.is_available():
            # Get GPU with most free memory
            gpu_memory = []
            for i in range(torch.cuda.device_count()):
                total_mem = torch.cuda.get_device_properties(i).total_memory
                used_mem = torch.cuda.memory_allocated(i)
                free_mem = total_mem - used_mem
                gpu_memory.append((i, free_mem))
            
            if gpu_memory:
                best_gpu = max(gpu_memory, key=lambda x: x[1])[0]
                logger.info(f"Using GPU {best_gpu} for inference")
                return torch.device(f"cuda:{best_gpu}")
        
        logger.info("Using CPU for inference")
        return torch.device("cpu")
    
    def get_memory_stats(self) -> Dict[str, float]:
        stats = {
            "cpu_percent": psutil.cpu_percent(),
            "ram_percent": psutil.virtual_memory().percent,
        }
        
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                allocated = torch.cuda.memory_allocated(i) / (1024 ** 3)  # GB
                stats[f"gpu_{i}_memory_gb"] = allocated
        
        self.memory_stats = stats
        return stats
    
    def clear_cache(self):
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
    @property
    def is_gpu_available(self) -> bool:
        return self.device.type.startswith("cuda")

@lru_cache()
def get_device_manager() -> DeviceManager:
    return DeviceManager() 
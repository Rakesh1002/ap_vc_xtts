import psutil
import gc
import logging
import torch
from app.core.config import get_settings
from typing import Optional
import threading
import time

logger = logging.getLogger(__name__)
settings = get_settings()

class MemoryManager:
    def __init__(self):
        self.settings = get_settings()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()

    def start_monitoring(self):
        """Start background memory monitoring"""
        if not self._cleanup_thread:
            self._cleanup_thread = threading.Thread(
                target=self._monitor_memory,
                daemon=True
            )
            self._cleanup_thread.start()

    def stop_monitoring(self):
        """Stop background memory monitoring"""
        if self._cleanup_thread:
            self._stop_cleanup.set()
            self._cleanup_thread.join()
            self._cleanup_thread = None

    def _monitor_memory(self):
        """Background memory monitoring loop"""
        while not self._stop_cleanup.is_set():
            try:
                self.check_memory()
                time.sleep(settings.MEMORY_CLEANUP_INTERVAL * 60)
            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

    def check_memory(self):
        """Check memory usage and clean up if necessary"""
        memory = psutil.virtual_memory()
        
        if memory.percent > settings.MAX_MEMORY_USAGE:
            logger.warning(f"High memory usage detected: {memory.percent}%")
            self.cleanup()
            
        if memory.available < settings.MIN_FREE_MEMORY * 1024 * 1024:
            logger.warning("Low available memory detected")
            self.cleanup(force=True)

    def cleanup(self, force: bool = False):
        """Clean up memory"""
        logger.info("Starting memory cleanup")
        
        # Clear Python garbage collector
        gc.collect()
        
        # Clear CUDA cache if using GPU
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        if force:
            # More aggressive cleanup
            gc.collect(generation=2)
            
            # Clear all unused tensors
            if torch.cuda.is_available():
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
                
            # Suggest Python garbage collection
            gc.collect()
        
        memory_after = psutil.virtual_memory()
        logger.info(f"Memory cleanup completed. Usage: {memory_after.percent}%")

    def get_memory_stats(self) -> dict:
        """Get current memory statistics"""
        vm = psutil.virtual_memory()
        gpu_stats = {}
        
        if torch.cuda.is_available():
            gpu_stats = {
                'gpu_allocated': f"{torch.cuda.memory_allocated() / 1024**2:.2f}MB",
                'gpu_cached': f"{torch.cuda.memory_reserved() / 1024**2:.2f}MB",
                'gpu_max_memory': f"{torch.cuda.max_memory_allocated() / 1024**2:.2f}MB"
            }
            
        return {
            'ram_used_percent': vm.percent,
            'ram_available': f"{vm.available / 1024**2:.2f}MB",
            'ram_total': f"{vm.total / 1024**2:.2f}MB",
            **gpu_stats
        }

memory_manager = MemoryManager()
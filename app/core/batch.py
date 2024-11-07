from typing import List, Any, Callable, TypeVar
import asyncio
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar('T')

class BatchProcessor:
    def __init__(self, batch_size: int = None):
        self.batch_size = batch_size or settings.BATCH_SIZE
        self.queue = asyncio.Queue()
        self._processing = False

    async def add_item(self, item: Any):
        """Add item to processing queue"""
        await self.queue.put(item)
        
        if not self._processing:
            self._processing = True
            asyncio.create_task(self._process_queue())

    async def process_batch(
        self,
        items: List[T],
        processor: Callable[[List[T]], Any]
    ) -> List[Any]:
        """Process a batch of items"""
        try:
            return await processor(items)
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            return []

    async def _process_queue(self):
        """Process items in batches"""
        batch = []
        
        while True:
            try:
                # Collect batch
                while len(batch) < self.batch_size:
                    try:
                        item = await asyncio.wait_for(
                            self.queue.get(),
                            timeout=1.0
                        )
                        batch.append(item)
                    except asyncio.TimeoutError:
                        break
                        
                if not batch:
                    self._processing = False
                    break
                    
                # Process batch
                await self.process_batch(batch, self._process_items)
                batch = []
                
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                await asyncio.sleep(1)

    async def _process_items(self, items: List[Any]):
        """Override this method to implement batch processing logic"""
        raise NotImplementedError

batch_processor = BatchProcessor() 
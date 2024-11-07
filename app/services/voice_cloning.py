from typing import Optional
import torch
from TTS.api import TTS
from TTS.utils.manage import ModelManager
from pathlib import Path
import boto3
from app.core.config import get_settings
import logging
import uuid
from app.core.device import get_device_manager
from app.core.metrics import MODEL_INFERENCE_TIME
from app.core.errors import AudioProcessingError, ErrorCodes
import time
import os
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)
settings = get_settings()

class VoiceCloningService:
    def __init__(self):
        self.device_manager = get_device_manager()
        self.model = self._initialize_model()
        self.storage_service = StorageService()

    def _initialize_model(self) -> TTS:
        try:
            # Check if model files exist
            model_path = Path(settings.XTTS_BASE_DIR)
            config_path = Path(settings.XTTS_CONFIG_PATH)
            
            # Log the paths we're checking
            logger.info(f"Checking model path: {model_path}")
            logger.info(f"Checking config path: {config_path}")
            
            # Check if files exist
            if not model_path.exists():
                raise AudioProcessingError(
                    message=f"XTTS model file not found at {model_path}",
                    error_code=ErrorCodes.MODEL_ERROR
                )
            
            if not config_path.exists():
                raise AudioProcessingError(
                    message=f"XTTS config file not found at {config_path}",
                    error_code=ErrorCodes.MODEL_ERROR
                )
            
            # Initialize TTS with local model path
            model = TTS(
                model_path=str(model_path),
                config_path=str(config_path),
                progress_bar=False,
                gpu=self.device_manager.is_gpu_available
            )
            logger.info("XTTS model initialized successfully")
            return model
            
        except Exception as e:
            error_msg = f"Failed to initialize XTTS model: {str(e)}"
            logger.exception(error_msg)
            raise AudioProcessingError(
                message=error_msg,
                error_code=ErrorCodes.MODEL_ERROR,
                original_error=e
            )

    async def clone_voice(
        self,
        voice_file_path: str,
        text: str,
        output_path: Optional[str] = None
    ) -> str:
        local_voice_path = None
        local_output_path = None
        
        try:
            # Log memory stats before inference
            mem_stats = self.device_manager.get_memory_stats()
            logger.info(f"Memory stats before inference: {mem_stats}")
            
            # Download voice file using StorageService
            local_voice_path = await self.storage_service.download_from_url(voice_file_path)
            
            # Generate output path if not provided
            local_output_path = Path(f"/tmp/generated_{uuid.uuid4()}.wav")
            
            # Generate speech with timing
            start_time = time.time()
            self.model.tts_to_file(
                text=text,
                speaker_wav=str(local_voice_path),
                file_path=str(local_output_path),
                language="en"
            )
            inference_time = time.time() - start_time
            
            # Record metrics
            MODEL_INFERENCE_TIME.labels(model_name="xtts_v2").observe(inference_time)
            
            # Upload to S3 using StorageService
            s3_path = f"outputs/{local_output_path.name}"
            await self.storage_service.upload_file(open(local_output_path, 'rb'), s3_path)
            
            # Log memory stats after inference
            mem_stats = self.device_manager.get_memory_stats()
            logger.info(f"Memory stats after inference: {mem_stats}")
            
            return s3_path
            
        except Exception as e:
            error_msg = f"Voice cloning failed: {str(e)}"
            logger.exception(error_msg)
            raise
        finally:
            # Cleanup
            if local_voice_path and Path(local_voice_path).exists():
                Path(local_voice_path).unlink()
            if local_output_path and local_output_path.exists():
                local_output_path.unlink()
            
            # Clear GPU cache if needed
            self.device_manager.clear_cache()
from faster_whisper import WhisperModel
from pathlib import Path
import boto3
from app.core.config import get_settings
import logging
from typing import Tuple, Optional
from app.core.device import get_device_manager
from app.core.metrics import MODEL_INFERENCE_TIME
from app.core.errors import AudioProcessingError, ErrorCodes
import time
import uuid
import torch
from huggingface_hub import snapshot_download
from app.services.storage_service import StorageService

settings = get_settings()
logger = logging.getLogger(__name__)

class TranslationService:
    def __init__(self):
        self.device_manager = get_device_manager()
        self.model = self._initialize_model()
        self.storage_service = StorageService()  # Use StorageService
        
    def _initialize_model(self) -> WhisperModel:
        try:
            # Correctly format the repo_id
            repo_id = "Systran/faster-whisper-large-v3"  # Use the correct namespace and repo name

            # Download the model using the correct repo_id
            model_dir = snapshot_download(repo_id=repo_id)

            # Initialize the Whisper model
            model = WhisperModel(model_dir)
            logger.info("Whisper model initialized successfully")
            return model

        except Exception as e:
            error_msg = f"Failed to initialize Whisper model: {str(e)}"
            logger.exception(error_msg)
            raise AudioProcessingError(
                message=error_msg,
                error_code=ErrorCodes.MODEL_ERROR,
                original_error=e
            )

    async def translate_audio(
        self,
        audio_path: str,
        target_language: str,
        source_language: Optional[str] = None
    ) -> Tuple[str, str]:
        local_audio_path = None
        
        try:
            # Log memory stats before inference
            mem_stats = self.device_manager.get_memory_stats()
            logger.info(f"Memory stats before translation: {mem_stats}")
            
            # Download audio file using StorageService
            local_audio_path = await self.storage_service.download_from_url(audio_path)
            
            # Transcribe and translate with timing
            start_time = time.time()
            segments, info = self.model.transcribe(
                str(local_audio_path),
                task="translate" if target_language != "en" else "transcribe",
                language=source_language,
                beam_size=5,  # Default beam size
                best_of=5    # Default best_of
            )
            inference_time = time.time() - start_time
            
            # Record metrics
            MODEL_INFERENCE_TIME.labels(model_name="whisper").observe(inference_time)
            
            # Combine segments and save transcript
            transcript = "\n".join([segment.text for segment in segments])
            transcript_path = f"transcripts/{Path(audio_path).stem}_{target_language}_{uuid.uuid4()}.txt"
            
            # Save transcript to S3 using StorageService
            await self.storage_service.upload_file(open(transcript_path, 'rb'), transcript_path)
            
            # Log memory stats after inference
            mem_stats = self.device_manager.get_memory_stats()
            logger.info(f"Memory stats after translation: {mem_stats}")
            
            return transcript_path, info.language
            
        except Exception as e:
            error_msg = f"Translation failed: {str(e)}"
            logger.exception(error_msg)
            raise AudioProcessingError(
                message=error_msg,
                error_code=ErrorCodes.PROCESSING_FAILED,
                original_error=e
            )
        finally:
            # Cleanup
            if local_audio_path and Path(local_audio_path).exists():
                Path(local_audio_path).unlink()
            
            # Clear GPU cache if needed
            self.device_manager.clear_cache()
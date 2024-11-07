from typing import Optional, Callable, BinaryIO
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
from app.core.errors import AudioProcessingError, ErrorCodes, ErrorSeverity
import time
import os
from app.services.storage_service import StorageService
import mimetypes
from functools import lru_cache

logger = logging.getLogger(__name__)
settings = get_settings()

class VoiceCloningService:
    _model_instance = None

    def __init__(self):
        self.device_manager = get_device_manager()
        self.storage_service = StorageService()
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION
        )
        self.bucket = settings.S3_BUCKET
        self.model = self._get_model()

    @staticmethod
    @lru_cache(maxsize=1)
    def _get_model() -> TTS:
        """Get or initialize the TTS model with caching"""
        if VoiceCloningService._model_instance is None:
            try:
                # Disable MPS on macOS
                if hasattr(torch.backends, 'mps'):
                    torch.backends.mps.enabled = False
                
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
                device = "cuda" if torch.cuda.is_available() else "cpu"
                VoiceCloningService._model_instance = TTS(
                    model_path=str(model_path),
                    config_path=str(config_path),
                    progress_bar=False,
                    gpu=torch.cuda.is_available()
                ).to(device)
                
                logger.info("XTTS model initialized successfully")
                
            except Exception as e:
                error_msg = f"Failed to initialize XTTS model: {str(e)}"
                logger.exception(error_msg)
                raise AudioProcessingError(
                    message=error_msg,
                    error_code=ErrorCodes.MODEL_ERROR,
                    original_error=e
                )
                
        return VoiceCloningService._model_instance

    async def clone_voice(
        self,
        voice_file_path: str,
        text: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> str:
        try:
            if progress_callback:
                progress_callback(0.1)  # Started
                
            # Log memory stats before inference
            mem_stats = self.device_manager.get_memory_stats()
            logger.info(f"Memory stats before cloning: {mem_stats}")
            
            # Download voice file
            if progress_callback:
                progress_callback(0.2)  # Downloading
                
            local_voice_path = await self.storage_service.download_from_url(voice_file_path)
            
            try:
                if progress_callback:
                    progress_callback(0.4)  # Processing
                    
                # Generate speech with timing
                start_time = time.time()
                output_path = output_path or f"outputs/cloned_{uuid.uuid4()}.wav"
                
                self.model.tts_to_file(
                    text=text,
                    speaker_wav=str(local_voice_path),
                    file_path=str(output_path),
                    language="en"
                )
                
                if progress_callback:
                    progress_callback(0.8)  # Generated
                
                inference_time = time.time() - start_time
                MODEL_INFERENCE_TIME.labels(model_name="xtts_v2").observe(inference_time)
                
                # Upload to S3
                s3_path = f"outputs/{Path(output_path).name}"
                await self.storage_service.upload_file(open(output_path, 'rb'), s3_path)
                
                if progress_callback:
                    progress_callback(1.0)  # Completed
                    
                return s3_path
                
            except Exception as e:
                raise AudioProcessingError(
                    message="Voice cloning failed",
                    error_code=ErrorCodes.PROCESSING_FAILED,
                    original_error=e,
                    severity=ErrorSeverity.HIGH
                )
            finally:
                # Cleanup
                if local_voice_path and Path(local_voice_path).exists():
                    Path(local_voice_path).unlink()
                if output_path and Path(output_path).exists():
                    Path(output_path).unlink()
                
                # Clear GPU cache if needed
                self.device_manager.clear_cache()
            
        except Exception as e:
            logger.exception("Voice cloning failed")
            raise AudioProcessingError(
                message=str(e),
                error_code=ErrorCodes.PROCESSING_FAILED,
                original_error=e
            )

    def clone_voice_sync(
        self,
        voice_file_path: str,
        text: str,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> str:
        """Synchronous version of voice cloning for Celery tasks"""
        try:
            if progress_callback:
                progress_callback(0.1)  # Started
                
            # Log memory stats before inference
            mem_stats = self.device_manager.get_memory_stats()
            logger.info(f"Memory stats before cloning: {mem_stats}")
            
            # Download voice file synchronously
            if progress_callback:
                progress_callback(0.2)  # Downloading
                
            local_voice_path = self._download_file_sync(voice_file_path)
            
            try:
                if progress_callback:
                    progress_callback(0.4)  # Processing
                    
                # Generate speech with timing
                start_time = time.time()
                output_path = f"outputs/cloned_{uuid.uuid4()}.wav"
                
                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Generate speech with XTTS
                self.model.tts_to_file(
                    text=text,
                    speaker_wav=str(local_voice_path),
                    file_path=str(output_path),
                    language="en"
                )
                
                if progress_callback:
                    progress_callback(0.8)  # Generated
                
                inference_time = time.time() - start_time
                MODEL_INFERENCE_TIME.labels(
                    model_name="xtts_v2",
                    operation="voice_cloning"
                ).observe(inference_time)
                
                # Upload to S3 synchronously
                s3_path = f"outputs/{Path(output_path).name}"
                with open(output_path, 'rb') as f:
                    self._upload_to_s3_sync(f, s3_path)
                
                if progress_callback:
                    progress_callback(1.0)  # Completed
                    
                return s3_path
                
            except Exception as e:
                raise AudioProcessingError(
                    message="Voice cloning failed",
                    error_code=ErrorCodes.PROCESSING_FAILED,
                    original_error=e,
                    severity=ErrorSeverity.HIGH
                )
            finally:
                # Cleanup
                if local_voice_path and Path(local_voice_path).exists():
                    Path(local_voice_path).unlink()
                if output_path and Path(output_path).exists():
                    Path(output_path).unlink()
                
                # Clear GPU cache if needed
                self.device_manager.clear_cache()
            
        except Exception as e:
            logger.exception("Voice cloning failed")
            raise AudioProcessingError(
                message=str(e),
                error_code=ErrorCodes.PROCESSING_FAILED,
                original_error=e
            )

    def _download_file_sync(self, file_path: str) -> str:
        """Synchronously download a file from S3"""
        try:
            local_path = os.path.join(settings.DOWNLOAD_DIR, Path(file_path).name)
            self.s3_client.download_file(self.bucket, file_path, local_path)
            return local_path
        except Exception as e:
            raise AudioProcessingError(
                message=f"Failed to download file: {str(e)}",
                error_code=ErrorCodes.DOWNLOAD_FAILED,
                original_error=e
            )

    def _upload_to_s3_sync(self, file: BinaryIO, key: str) -> str:
        """Synchronously upload a file to S3"""
        try:
            content_type, _ = mimetypes.guess_type(key)
            content_type = content_type or 'application/octet-stream'
            
            transfer_config = boto3.s3.transfer.TransferConfig(
                multipart_threshold=settings.MULTIPART_THRESHOLD,
                multipart_chunksize=settings.MULTIPART_CHUNKSIZE,
                max_concurrency=settings.MAX_CONCURRENCY
            )
            
            self.s3_client.upload_fileobj(
                file,
                self.bucket,
                key,
                ExtraArgs={'ContentType': content_type},
                Config=transfer_config
            )
            
            return f"https://{self.bucket}.s3.amazonaws.com/{key}"
        except Exception as e:
            raise AudioProcessingError(
                message=f"Failed to upload file: {str(e)}",
                error_code=ErrorCodes.UPLOAD_FAILED,
                original_error=e
            )
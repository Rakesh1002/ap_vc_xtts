import torch
import torchaudio
from denoiser import pretrained
from denoiser.dsp import convert_audio
import numpy as np
import logging
from typing import Dict, Any
from pathlib import Path
import tempfile
from functools import wraps
from app.core.errors import DenoiserError, ErrorCodes
from app.db.session import AsyncSessionLocal
from app.models.audio import DenoiseJob, ProcessingStatus
from app.services.storage_service import StorageService
import gc
import os
import soundfile as sf
import subprocess
from pydub import AudioSegment
import io
from app.core.constants import MAX_AUDIO_SIZE, MIN_AUDIO_DURATION, MAX_AUDIO_DURATION, SUPPORTED_AUDIO_FORMATS, SUPPORTED_AUDIO_EXTENSIONS, PROCESSING_SAMPLE_RATE, PROCESSING_CHANNELS, PROCESSING_FORMAT

logger = logging.getLogger(__name__)

def optimize_array_processing(func):
    """Decorator to optimize array processing operations"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            result = await func(*args, **kwargs)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            return result
        except Exception as e:
            logger.error(f"Error in array processing: {str(e)}")
            raise
    return wrapper

class DenoiserService:
    """Service for audio denoising using Denoiser"""
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DenoiserService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize service"""
        try:
            # Load model based on available hardware
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Initializing Denoiser model on {device}")
            
            try:
                self._model = pretrained.dns64()
                self._model = self._model.to(device)
                self._model.eval()
            except Exception as e:
                logger.error(f"Failed to load DNS64 model: {str(e)}")
                self.initialized = False
                raise DenoiserError(
                    message="Failed to initialize denoiser model",
                    error_code=ErrorCodes.INIT_ERROR,
                    details=str(e)
                )
            
            self.device = device
            self.storage_service = StorageService()
            self.initialized = True
            logger.info(f"Denoiser initialized successfully on {device}")
            
        except Exception as e:
            self.initialized = False
            logger.error(f"Denoiser initialization failed: {str(e)}")
            logger.exception("Full traceback:")
            self._model = None
            self.storage_service = None
            # Don't raise here, just log the error and set initialized to False

    @optimize_array_processing
    async def process_audio(
        self,
        input_path: str,
        output_path: str
    ) -> Dict[str, Any]:
        """Process audio file with Denoiser"""
        temp_input = None
        temp_output = None
        
        try:
            # Create temporary files for format conversion
            temp_input = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_output = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            
            # Convert input to proper format
            audio_info = await self.convert_audio_format(input_path, temp_input.name)
            
            # Process with existing code
            result = await self._process_audio(temp_input.name, temp_output.name)
            
            # Convert output back if needed
            await self.convert_audio_format(temp_output.name, output_path)
            
            # Update stats with audio info
            result["stats"].update(audio_info)
            
            return result
            
        finally:
            # Cleanup temp files
            for temp_file in [temp_input, temp_output]:
                if temp_file:
                    try:
                        temp_file.close()
                        if os.path.exists(temp_file.name):
                            os.unlink(temp_file.name)
                    except Exception as e:
                        logger.warning(f"Failed to cleanup temp file: {e}")

    async def _process_audio(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """Internal audio processing method"""
        try:
            # Load audio file
            wav, sr = torchaudio.load(input_path)
            
            # Convert to model format
            wav = convert_audio(
                wav.to(self.device), 
                sr, 
                self._model.sample_rate, 
                self._model.chin
            )
            
            # Process in chunks if audio is too long
            chunk_size = 10 * self._model.sample_rate  # 10 second chunks
            denoised_chunks = []
            
            with torch.no_grad():
                for i in range(0, wav.shape[1], chunk_size):
                    chunk = wav[:, i:i + chunk_size]
                    if chunk.shape[1] < 100:  # Skip very small chunks
                        continue
                        
                    # Process chunk
                    denoised_chunk = self._model(chunk[None])[0]
                    denoised_chunks.append(denoised_chunk.cpu())
                    
                    # Clear GPU memory
                    if self.device == "cuda":
                        torch.cuda.empty_cache()
            
            # Combine chunks
            denoised = torch.cat(denoised_chunks, dim=1)
            
            # Save output
            torchaudio.save(
                output_path,
                denoised.cpu(),
                self._model.sample_rate
            )
            
            # Calculate stats
            stats = {
                "original_duration": wav.shape[1] / self._model.sample_rate,
                "denoised_duration": denoised.shape[1] / self._model.sample_rate,
                "sample_rate": self._model.sample_rate,
                "noise_reduction_db": self._calculate_noise_reduction(
                    wav.cpu().numpy(),
                    denoised.cpu().numpy()
                )
            }
            
            return {
                "output_path": output_path,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Failed to process audio: {str(e)}")
            raise DenoiserError(
                message="Failed to process audio",
                error_code=ErrorCodes.PROCESSING_ERROR,
                details={"error": str(e)}
            )
        finally:
            # Clear memory
            if self.device == "cuda":
                torch.cuda.empty_cache()
            gc.collect()

    def _calculate_noise_reduction(
        self, 
        original: np.ndarray, 
        denoised: np.ndarray
    ) -> float:
        """Calculate noise reduction in dB"""
        noise = original - denoised
        noise_rms = np.sqrt(np.mean(noise ** 2))
        signal_rms = np.sqrt(np.mean(denoised ** 2))
        
        if noise_rms > 0:
            return float(20 * np.log10(signal_rms / noise_rms))
        return 0.0

    async def get_job_status(self, job_id: int) -> Dict[str, Any]:
        """Get status of a denoising job with presigned URL if completed"""
        if not self.initialized:
            raise DenoiserError(
                message="Denoiser service not initialized",
                error_code=ErrorCodes.INIT_ERROR
            )

        async with AsyncSessionLocal() as db:
            job = await db.get(DenoiseJob, job_id)
            if not job:
                raise DenoiserError(
                    message=f"Job {job_id} not found",
                    error_code=ErrorCodes.NOT_FOUND
                )
            
            # Generate presigned URL if completed
            if job.status == ProcessingStatus.COMPLETED and job.output_path:
                try:
                    output_url = await self.storage_service.get_presigned_url(
                        job.output_path,
                        expiry=3600
                    )
                except Exception as e:
                    logger.error(f"Failed to generate presigned URL: {str(e)}")
                    output_url = None
            else:
                output_url = None
                
            return {
                "status": job.status,
                "output_url": output_url,
                "stats": job.stats,
                "error_message": job.error_message
            }

    async def convert_audio_format(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """Convert audio to the required format for processing"""
        try:
            # Try using pydub first for better format support
            try:
                audio = AudioSegment.from_file(input_path)
                
                # Convert to mono if needed
                if audio.channels > 1:
                    audio = audio.set_channels(PROCESSING_CHANNELS)
                
                # Set sample rate
                if audio.frame_rate != PROCESSING_SAMPLE_RATE:
                    audio = audio.set_frame_rate(PROCESSING_SAMPLE_RATE)
                
                # Export as WAV
                audio.export(output_path, format=PROCESSING_FORMAT, parameters=[
                    "-acodec", "pcm_s16le",  # Force 16-bit PCM encoding
                    "-ar", str(PROCESSING_SAMPLE_RATE),
                    "-ac", str(PROCESSING_CHANNELS)
                ])
                
                return {
                    "duration": len(audio) / 1000.0,
                    "sample_rate": audio.frame_rate,
                    "channels": audio.channels,
                    "format": "wav"
                }
                
            except Exception as e:
                logger.warning(f"Pydub conversion failed, trying FFmpeg: {e}")
                
                # Fallback to FFmpeg with more explicit parameters
                cmd = [
                    'ffmpeg', '-y',
                    '-i', input_path,
                    '-vn',  # No video
                    '-acodec', 'pcm_s16le',  # Force 16-bit PCM
                    '-ar', str(PROCESSING_SAMPLE_RATE),
                    '-ac', str(PROCESSING_CHANNELS),
                    '-af', 'aresample=resampler=soxr',  # High quality resampling
                    output_path
                ]
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    raise DenoiserError(
                        message="Audio conversion failed",
                        error_code=ErrorCodes.AUDIO_CONVERSION_FAILED,
                        details={"error": stderr.decode()}
                    )
                
                # Verify the converted file
                with sf.SoundFile(output_path) as f:
                    return {
                        "duration": float(len(f)) / f.samplerate,
                        "sample_rate": f.samplerate,
                        "channels": f.channels,
                        "format": "wav"
                    }
                
        except Exception as e:
            raise DenoiserError(
                message="Failed to convert audio format",
                error_code=ErrorCodes.AUDIO_CONVERSION_FAILED,
                details={"error": str(e)}
            )

    def validate_audio_file(self, file_path: str) -> Dict[str, Any]:
        """Validate audio file before processing"""
        try:
            # Check file exists
            if not os.path.exists(file_path):
                raise DenoiserError(
                    message="Audio file not found",
                    error_code=ErrorCodes.NOT_FOUND
                )
                
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > MAX_AUDIO_SIZE:
                raise DenoiserError(
                    message="Audio file too large",
                    error_code=ErrorCodes.FILE_TOO_LARGE,
                    details={"max_size": MAX_AUDIO_SIZE, "file_size": file_size}
                )
                
            # Try to read file with soundfile first
            try:
                with sf.SoundFile(file_path) as f:
                    duration = float(len(f)) / f.samplerate
                    audio_info = {
                        "duration": duration,
                        "sample_rate": f.samplerate,
                        "channels": f.channels,
                        "format": f.format
                    }
            except Exception:
                # If soundfile fails, try pydub
                try:
                    audio = AudioSegment.from_file(file_path)
                    duration = len(audio) / 1000.0  # Convert ms to seconds
                    audio_info = {
                        "duration": duration,
                        "sample_rate": audio.frame_rate,
                        "channels": audio.channels,
                        "format": audio.channels
                    }
                except Exception as e:
                    raise DenoiserError(
                        message="Invalid audio file",
                        error_code=ErrorCodes.INVALID_AUDIO_FORMAT,
                        details={"error": str(e)}
                    )
            
            # Validate duration
            if duration < MIN_AUDIO_DURATION:
                raise DenoiserError(
                    message="Audio too short",
                    error_code=ErrorCodes.AUDIO_TOO_SHORT,
                    details={"min_duration": MIN_AUDIO_DURATION, "duration": duration}
                )
                
            if duration > MAX_AUDIO_DURATION:
                raise DenoiserError(
                    message="Audio too long",
                    error_code=ErrorCodes.AUDIO_TOO_LONG,
                    details={"max_duration": MAX_AUDIO_DURATION, "duration": duration}
                )
                
            return audio_info
                
        except DenoiserError:
            raise
        except Exception as e:
            raise DenoiserError(
                message="Failed to validate audio file",
                error_code=ErrorCodes.AUDIO_VALIDATION_FAILED,
                details={"error": str(e)}
            )
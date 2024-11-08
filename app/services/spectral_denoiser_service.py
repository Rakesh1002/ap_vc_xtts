import numpy as np
import soundfile as sf
import logging
from typing import Dict, Any, Optional, NamedTuple
from pathlib import Path
import noisereduce as nr
from app.core.errors import DenoiserError, ErrorCodes
from app.core.metrics import (
    SPECTRAL_DENOISING_TIME,
    SPECTRAL_NOISE_REDUCTION
)
from app.services.storage_service import StorageService
from app.models.audio import DenoiseJob, ProcessingStatus
from app.db.session import AsyncSessionLocal
import torch
import gc
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class NoiseType(str, Enum):
    WHITE_NOISE = "white_noise"
    STREET_NOISE = "street_noise"
    BACKGROUND_CHATTER = "background_chatter"
    ROOM_NOISE = "room_noise"
    AIR_CONDITIONING = "air_conditioning"
    MACHINE_HUM = "machine_hum"
    WIND_NOISE = "wind_noise"
    GENERAL = "general"

@dataclass
class DenoisePreset:
    prop_decrease: float
    time_constant_s: float
    freq_mask_smooth_hz: int
    time_mask_smooth_ms: int
    stationary: bool
    two_pass: bool = True
    second_pass_params: Optional[Dict] = None

class NoisePresets:
    WHITE_NOISE = DenoisePreset(
        prop_decrease=0.95,
        time_constant_s=1.5,
        freq_mask_smooth_hz=200,
        time_mask_smooth_ms=100,
        stationary=True,
        two_pass=True,
        second_pass_params={
            "prop_decrease": 0.5,
            "time_constant_s": 0.75,
            "freq_mask_smooth_hz": 100,
            "time_mask_smooth_ms": 50
        }
    )
    
    STREET_NOISE = DenoisePreset(
        prop_decrease=0.98,
        time_constant_s=2.0,
        freq_mask_smooth_hz=300,
        time_mask_smooth_ms=150,
        stationary=False,
        two_pass=True,
        second_pass_params={
            "prop_decrease": 0.6,
            "time_constant_s": 1.0,
            "freq_mask_smooth_hz": 150,
            "time_mask_smooth_ms": 75
        }
    )
    
    BACKGROUND_CHATTER = DenoisePreset(
        prop_decrease=0.90,
        time_constant_s=1.0,
        freq_mask_smooth_hz=400,
        time_mask_smooth_ms=50,
        stationary=False,  # Non-stationary for varying speech
        two_pass=True,
        second_pass_params={
            "prop_decrease": 0.5,
            "time_constant_s": 0.5,
            "freq_mask_smooth_hz": 200,
            "time_mask_smooth_ms": 25
        }
    )
    
    ROOM_NOISE = DenoisePreset(
        prop_decrease=0.85,
        time_constant_s=1.5,
        freq_mask_smooth_hz=150,
        time_mask_smooth_ms=75,
        stationary=True
    )
    
    AIR_CONDITIONING = DenoisePreset(
        prop_decrease=0.95,
        time_constant_s=2.0,
        freq_mask_smooth_hz=250,
        time_mask_smooth_ms=200,
        stationary=True
    )
    
    MACHINE_HUM = DenoisePreset(
        prop_decrease=0.98,
        time_constant_s=2.5,
        freq_mask_smooth_hz=100,
        time_mask_smooth_ms=250,
        stationary=True
    )
    
    WIND_NOISE = DenoisePreset(
        prop_decrease=0.92,
        time_constant_s=1.0,
        freq_mask_smooth_hz=500,
        time_mask_smooth_ms=100,
        stationary=False
    )
    
    GENERAL = DenoisePreset(
        prop_decrease=0.90,
        time_constant_s=1.5,
        freq_mask_smooth_hz=200,
        time_mask_smooth_ms=100,
        stationary=True
    )

class SpectralDenoiserService:
    """Service for audio denoising using noisereduce spectral gating"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SpectralDenoiserService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize service"""
        try:
            self.storage_service = StorageService()
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.initialized = True
            logger.info(f"Spectral denoiser service initialized successfully using device: {self.device}")
        except Exception as e:
            self.initialized = False
            logger.error(f"Spectral denoiser service initialization failed: {str(e)}")
            self.storage_service = None

    def _calculate_noise_reduction(
        self, 
        original: np.ndarray, 
        denoised: np.ndarray
    ) -> float:
        """Calculate noise reduction in dB"""
        try:
            # Calculate RMS of noise reduction
            noise = original - denoised
            noise_rms = np.sqrt(np.mean(noise ** 2))
            signal_rms = np.sqrt(np.mean(denoised ** 2))
            
            if noise_rms > 0:
                return float(20 * np.log10(signal_rms / noise_rms))
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating noise reduction: {e}")
            return 0.0

    def process_audio(
        self,
        input_path: str,
        output_path: str,
        noise_type: NoiseType = NoiseType.GENERAL,
        custom_params: Optional[Dict] = None,
        use_torch: bool = True
    ) -> Dict[str, Any]:
        """Process audio file with spectral gating denoising optimized for specific noise types"""
        try:
            # Get preset for noise type
            preset = getattr(NoisePresets, noise_type.upper())
            
            # Override with custom params if provided
            params = {
                "prop_decrease": preset.prop_decrease,
                "time_constant_s": preset.time_constant_s,
                "freq_mask_smooth_hz": preset.freq_mask_smooth_hz,
                "time_mask_smooth_ms": preset.time_mask_smooth_ms,
                "stationary": preset.stationary
            }
            if custom_params:
                params.update(custom_params)

            # Clear memory
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

            # Read and prepare audio
            audio_data, sample_rate = sf.read(input_path)
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)
            audio_data = audio_data.astype(np.float32)

            # First pass denoising
            denoised_audio = nr.reduce_noise(
                y=audio_data,
                sr=sample_rate,
                use_torch=use_torch,
                device=str(self.device),
                **params
            )

            # Second pass if specified in preset
            if preset.two_pass and preset.second_pass_params:
                denoised_audio = nr.reduce_noise(
                    y=denoised_audio,
                    sr=sample_rate,
                    use_torch=use_torch,
                    device=str(self.device),
                    **preset.second_pass_params
                )

            # Save output
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, denoised_audio, sample_rate)

            # Calculate stats
            stats = {
                "original_duration": len(audio_data) / sample_rate,
                "denoised_duration": len(denoised_audio) / sample_rate,
                "sample_rate": sample_rate,
                "noise_reduction_db": self._calculate_noise_reduction(audio_data, denoised_audio),
                "noise_type": noise_type,
                "preset_used": preset.__dict__,
                "custom_params": custom_params,
                "two_pass": preset.two_pass
            }

            return {
                "output_path": output_path,
                "stats": stats
            }

        except Exception as e:
            logger.error(f"Failed to process audio: {str(e)}")
            raise DenoiserError(
                f"Failed to process audio: {str(e)}",
                error_code=ErrorCodes.DENOISING_FAILED
            )

    async def get_job_status(self, job_id: int) -> Dict[str, Any]:
        """Get status of a denoising job"""
        if not self.initialized:
            raise DenoiserError(
                message="Spectral denoiser service not initialized",
                error_code=ErrorCodes.DENOISING_FAILED
            )

        async with AsyncSessionLocal() as db:
            job = await db.get(DenoiseJob, job_id)
            if not job:
                raise DenoiserError(
                    message=f"Job {job_id} not found",
                    error_code=ErrorCodes.NOT_FOUND
                )
            
            # Generate presigned URL only if completed
            if job.status == ProcessingStatus.COMPLETED and job.output_path:
                try:
                    output_url = await self.storage_service.get_presigned_url(
                        job.output_path,
                        expiry=3600  # 1 hour
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
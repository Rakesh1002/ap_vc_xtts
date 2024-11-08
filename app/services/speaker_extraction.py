import os
import tempfile
import magic
import subprocess
from pydub import AudioSegment
from pyannote.audio import Pipeline
from huggingface_hub import hf_hub_download
import torch
import torchaudio
import scipy.io.wavfile as wavfile
import io
import logging
from typing import Dict, Any, Tuple
from app.core.config import get_settings
from app.services.storage_service import StorageService
from app.core.errors import AudioProcessingError, ErrorCodes
from pyannote.audio.pipelines.utils.hook import ProgressHook
from app.core.metrics import SPEAKER_EXTRACTION_TIME, SPEAKER_COUNT
import gc
import numpy as np

logger = logging.getLogger(__name__)
settings = get_settings()

class SpeakerExtractionService:
    def __init__(self):
        self.storage = StorageService()
        self.hf_token = settings.HF_TOKEN
        if not self.hf_token:
            raise ValueError("HF_TOKEN environment variable is not set")
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        self.pipeline = self._initialize_pipeline()

    def __del__(self):
        if hasattr(self, 'pipeline'):
            del self.pipeline
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _initialize_pipeline(self) -> Pipeline:
        """Initialize the pyannote separation pipeline"""
        try:
            model_path = hf_hub_download(
                repo_id="pyannote/speech-separation-ami-1.0",
                filename="config.yaml",
                use_auth_token=self.hf_token
            )
            logger.info(f"Model downloaded to: {model_path}")
            
            pipeline = Pipeline.from_pretrained(
                model_path,
                use_auth_token=self.hf_token
            )
            
            if torch.cuda.is_available():
                pipeline = pipeline.to(self.device)
                logger.info(f"Pipeline moved to GPU: {torch.cuda.get_device_name(0)}")
            else:
                logger.info("Using CPU for inference")
            
            return pipeline
            
        except Exception as e:
            logger.error(f"Pipeline initialization failed: {str(e)}")
            raise AudioProcessingError(
                message=f"Failed to initialize pipeline: {str(e)}",
                error_code=ErrorCodes.MODEL_ERROR
            )

    async def process_audio(self, input_path: str) -> Dict[str, Any]:
        """Process audio file for speaker extraction"""
        try:
            # Download audio file
            audio_data = await self.storage.download_file(input_path)
            waveform, sample_rate = await self._load_audio(audio_data)
            
            # Log GPU memory if available
            self._log_gpu_memory()
            
            # Resample if needed
            if sample_rate != settings.AUDIO_SAMPLE_RATE:
                waveform = await self._resample_audio(waveform, sample_rate, settings.AUDIO_SAMPLE_RATE)
                sample_rate = settings.AUDIO_SAMPLE_RATE

            # Process with pipeline
            logger.info("Running pipeline...")
            with ProgressHook() as hook:
                diarization, sources = self.pipeline({
                    "waveform": waveform,
                    "sample_rate": sample_rate
                }, hook=hook)
            logger.info("Pipeline execution completed")
            
            # Generate job ID from input path
            job_id = input_path.split('/')[-2]  # Assuming path format: uploads/speaker_extraction/{job_id}/file.wav
            
            # Save results
            results = await self._save_results(job_id, diarization, sources, sample_rate)
            
            # Record metrics
            SPEAKER_COUNT.labels(job_type="extraction").observe(len(results["speakers"]))
            
            # Cleanup
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
            
            return results
            
        except Exception as e:
            logger.error(f"Speaker extraction failed: {str(e)}")
            raise AudioProcessingError(
                message=f"Failed to extract speakers: {str(e)}",
                error_code=ErrorCodes.PROCESSING_FAILED
            )

    async def _load_audio(self, audio_data: bytes) -> Tuple[torch.Tensor, int]:
        """Load audio data with fallback methods"""
        try:
            # Try torchaudio first
            with io.BytesIO(audio_data) as buffer:
                try:
                    waveform, sample_rate = torchaudio.load(buffer)
                    return waveform, sample_rate
                except Exception as e:
                    logger.warning(f"torchaudio load failed: {e}")

            # Fallback to pydub/ffmpeg
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name

            # Convert to WAV if needed
            file_type = magic.from_file(temp_path, mime=True)
            if not file_type.startswith('audio/x-wav'):
                wav_path = f"{temp_path}_converted.wav"
                subprocess.run([
                    'ffmpeg', '-i', temp_path,
                    '-acodec', 'pcm_s16le',
                    '-ar', str(settings.AUDIO_SAMPLE_RATE),
                    wav_path
                ], check=True, capture_output=True)
                os.remove(temp_path)
                temp_path = wav_path

            # Load with pydub
            audio = AudioSegment.from_wav(temp_path)
            samples = torch.FloatTensor(audio.get_array_of_samples())
            
            # Handle channels
            if audio.channels > 1:
                samples = samples.view(-1, audio.channels).t()
            else:
                samples = samples.unsqueeze(0)

            os.remove(temp_path)
            return samples, audio.frame_rate

        except Exception as e:
            raise AudioProcessingError(
                message=f"Failed to load audio: {str(e)}",
                error_code=ErrorCodes.INVALID_AUDIO_FORMAT
            )

    async def _resample_audio(
        self, 
        waveform: torch.Tensor, 
        orig_sr: int, 
        target_sr: int
    ) -> torch.Tensor:
        """Resample audio to target sample rate"""
        resampler = torchaudio.transforms.Resample(orig_sr, target_sr)
        return resampler(waveform)

    def _log_gpu_memory(self):
        """Log GPU memory usage"""
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            logger.info(f"GPU Memory: Allocated {allocated:.2f}GB, Reserved {reserved:.2f}GB")

    async def _save_results(
        self,
        job_id: int,
        diarization: Any,
        sources: Any,
        sample_rate: int
    ) -> Dict[str, Any]:
        """Save diarization results and separated audio files with normalization"""
        results = {
            "speakers": [],
            "files": []
        }

        # Save RTTM file
        rttm_path = f"processed/{job_id}/extraction.rttm"
        rttm_buffer = io.StringIO()
        diarization.write_rttm(rttm_buffer)
        await self.storage.upload_file(
            rttm_buffer.getvalue().encode(), 
            rttm_path
        )
        results["files"].append({
            "type": "rttm",
            "path": rttm_path
        })

        # Process and save individual speaker audio
        for idx, speaker in enumerate(diarization.labels()):
            speaker_path = f"processed/{job_id}/speaker_{idx}.wav"
            
            # Get speaker audio
            speaker_audio = sources.data[:, idx]
            if isinstance(speaker_audio, torch.Tensor):
                speaker_audio = speaker_audio.cpu().numpy()
            
            # Apply audio normalization
            normalized_audio = self._normalize_audio(speaker_audio)
            
            # Get audio stats for logging
            original_rms = np.sqrt(np.mean(np.square(speaker_audio)))
            final_rms = np.sqrt(np.mean(np.square(normalized_audio)))
            logger.info(
                f"Speaker {idx} normalization - "
                f"Original RMS: {20 * np.log10(original_rms):.2f} dB, "
                f"Final RMS: {20 * np.log10(final_rms):.2f} dB"
            )
            
            # Save normalized audio
            buffer = io.BytesIO()
            wavfile.write(
                buffer,
                sample_rate,
                (normalized_audio * np.iinfo(np.int16).max).astype(np.int16)
            )
            buffer.seek(0)
            
            # Upload to storage
            await self.storage.upload_file(
                buffer.getvalue(),
                speaker_path
            )
            
            # Add to results
            results["speakers"].append({
                "id": idx,
                "label": speaker,
                "audio_path": speaker_path,
                "audio_stats": {
                    "rms_db": float(20 * np.log10(final_rms)),
                    "peak": float(np.max(np.abs(normalized_audio)))
                }
            })
            results["files"].append({
                "type": "audio",
                "speaker": speaker,
                "path": speaker_path
            })

        return results

    def _normalize_audio(self, waveform: np.ndarray, target_db: float = -18.0) -> np.ndarray:
        """Normalize audio using RMS normalization with peak limiting"""
        # Calculate current RMS
        rms = np.sqrt(np.mean(np.square(waveform)))
        
        # Calculate target RMS (convert from dB)
        target_rms = 10 ** (target_db / 20.0)
        
        # Calculate gain needed
        gain = target_rms / (rms + 1e-6)  # Avoid division by zero
        
        # Apply gain
        normalized = waveform * gain
        
        # Apply peak limiting to prevent clipping
        max_peak = np.max(np.abs(normalized))
        if max_peak > 0.95:  # Leave some headroom
            normalized = normalized * (0.95 / max_peak)
        
        return normalized
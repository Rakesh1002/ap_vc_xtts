from pyannote.audio import Pipeline
from huggingface_hub import hf_hub_download
import torch
import torchaudio
import io
import logging
from typing import Dict, Any, Tuple
from app.core.config import get_settings
from app.services.storage_service import StorageService
from app.core.errors import AudioProcessingError
from pyannote.audio.pipelines.utils.hook import ProgressHook

logger = logging.getLogger(__name__)
settings = get_settings()

class SpeakerDiarizationService:
    """Service for speaker diarization using pyannote/speaker-diarization-3.1"""
    
    def __init__(self):
        self.storage = StorageService()
        self.hf_token = settings.HF_TOKEN
        if not self.hf_token:
            raise ValueError("HF_TOKEN environment variable is not set")
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.pipeline = self._initialize_pipeline()

    def __del__(self):
        if hasattr(self, 'pipeline'):
            del self.pipeline
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _initialize_pipeline(self) -> Pipeline:
        """Initialize the pyannote diarization pipeline"""
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token
            )
            
            if torch.cuda.is_available():
                pipeline = pipeline.to(self.device)
                logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
            
            return pipeline
        except Exception as e:
            logger.error(f"Pipeline initialization failed: {str(e)}")
            raise AudioProcessingError(f"Failed to initialize pipeline: {str(e)}")

    async def process_audio(self, job_id: int, input_path: str, num_speakers: int = None) -> Dict[str, Any]:
        """Process audio file for speaker diarization"""
        try:
            # Download from storage
            audio_data = self.storage.download_file(input_path)
            waveform, sample_rate = await self._load_audio(audio_data)
            
            # Resample if needed
            if sample_rate != 16000:
                waveform = await self._resample_audio(waveform, sample_rate, 16000)
                sample_rate = 16000

            # Run diarization
            with ProgressHook() as hook:
                if num_speakers:
                    diarization = self.pipeline(
                        {"waveform": waveform, "sample_rate": sample_rate},
                        num_speakers=num_speakers,
                        hook=hook
                    )
                else:
                    diarization = self.pipeline(
                        {"waveform": waveform, "sample_rate": sample_rate},
                        hook=hook
                    )

            # Save results
            results = await self._save_results(job_id, diarization)
            
            return {
                "status": "completed",
                "num_speakers": len(diarization.labels()),
                "results": results
            }

        except Exception as e:
            logger.error(f"Audio processing failed: {str(e)}")
            raise AudioProcessingError(f"Failed to process audio: {str(e)}")
        finally:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    async def _load_audio(self, audio_data: bytes) -> Tuple[torch.Tensor, int]:
        """Load audio data into memory"""
        try:
            with io.BytesIO(audio_data) as buffer:
                waveform, sample_rate = torchaudio.load(buffer)
                return waveform, sample_rate
        except Exception as e:
            raise AudioProcessingError(f"Failed to load audio: {str(e)}")

    async def _resample_audio(
        self, 
        waveform: torch.Tensor, 
        orig_sr: int, 
        target_sr: int
    ) -> torch.Tensor:
        """Resample audio to target sample rate"""
        resampler = torchaudio.transforms.Resample(orig_sr, target_sr)
        return resampler(waveform)

    async def _save_results(
        self,
        job_id: int,
        diarization: Any,
    ) -> Dict[str, Any]:
        """Save diarization results"""
        results = {
            "speakers": [],
            "timeline": []
        }

        # Save RTTM file
        rttm_path = f"processed/{job_id}/diarization.rttm"
        rttm_buffer = io.StringIO()
        diarization.write_rttm(rttm_buffer)
        await self.storage.upload_file(
            rttm_buffer.getvalue().encode(), 
            rttm_path
        )
        
        # Process timeline
        for segment, track, speaker in diarization.itertracks(yield_label=True):
            results["timeline"].append({
                "start": segment.start,
                "end": segment.end,
                "speaker": speaker
            })
        
        # Collect unique speakers
        for speaker in diarization.labels():
            total_time = sum(
                segment.end - segment.start
                for segment, _, spk in diarization.itertracks(yield_label=True)
                if spk == speaker
            )
            results["speakers"].append({
                "label": speaker,
                "total_speaking_time": total_time
            })

        return results
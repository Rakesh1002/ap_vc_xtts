from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobType(str, Enum):
    VOICE_CLONING = "voice_cloning"
    TRANSLATION = "translation"
    SPEAKER_DIARIZATION = "speaker_diarization"
    SPEAKER_EXTRACTION = "speaker_extraction"
    DENOISING = "denoising"

class VoiceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class VoiceCreate(VoiceBase):
    pass

class Voice(VoiceBase):
    id: int
    file_path: str
    created_at: datetime

    class Config:
        from_attributes = True

class CloningJobCreate(BaseModel):
    voice_id: int
    input_text: str = Field(..., min_length=1, max_length=5000, description="Text to be converted to speech")

    class Config:
        json_schema_extra = {
            "example": {
                "voice_id": 1,
                "input_text": "Hello world, this is a test message."
            }
        }

class CloningJob(BaseModel):
    id: int
    voice_id: int
    status: ProcessingStatus
    input_text: str
    output_path: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

class TranslationJobCreate(BaseModel):
    target_language: str = Field(..., min_length=2, max_length=5)
    source_language: Optional[str] = Field(None, min_length=2, max_length=5)

class TranslationJob(BaseModel):
    id: int
    status: ProcessingStatus
    source_language: Optional[str]
    target_language: str
    input_path: str
    transcript_path: Optional[str]
    audio_output_path: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

class DenoiseRequest(BaseModel):
    vad_threshold: Optional[float] = Field(0.5, ge=0.0, le=1.0)

    @validator('vad_threshold')
    def validate_threshold(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("VAD threshold must be between 0.0 and 1.0")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "vad_threshold": 0.5
            }
        }

class DenoiseResponse(BaseModel):
    status: str
    output_url: str
    stats: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "output_url": "https://storage.example.com/denoised/audio_denoised.wav",
                "stats": {
                    "original_duration": 10.5,
                    "denoised_duration": 10.5,
                    "sample_rate": 48000,
                    "noise_reduction_db": 15.3,
                    "vad_confidence": 0.85
                }
            }
        }

class DenoiseJob(BaseModel):
    """Schema for denoising job responses"""
    id: int
    status: ProcessingStatus
    input_path: str
    output_path: Optional[str] = None
    task_id: Optional[str] = None
    error_message: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output_url: Optional[str] = None  # For presigned URLs

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class SpectralDenoiseRequest(BaseModel):
    stationary: bool = Field(True, description="Whether to use stationary noise reduction")
    prop_decrease: float = Field(1.0, ge=0.0, le=1.0, description="Proportion to decrease noise by")
    time_constant_s: float = Field(2.0, gt=0.0, description="Time constant in seconds")
    freq_mask_smooth_hz: int = Field(500, gt=0, description="Frequency mask smoothing in Hz")
    time_mask_smooth_ms: int = Field(50, gt=0, description="Time mask smoothing in ms")

    class Config:
        json_schema_extra = {
            "example": {
                "stationary": True,
                "prop_decrease": 1.0,
                "time_constant_s": 2.0,
                "freq_mask_smooth_hz": 500,
                "time_mask_smooth_ms": 50
            }
        }
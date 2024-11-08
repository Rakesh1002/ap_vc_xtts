from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum
from app.models.audio import ProcessingStatus

class SpeakerJobType(str, Enum):
    DIARIZATION = "diarization"
    EXTRACTION = "extraction"

class SpeakerSegment(BaseModel):
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    speaker: str = Field(..., description="Speaker identifier")

class SpeakerInfo(BaseModel):
    label: str = Field(..., description="Speaker label/identifier")
    total_speaking_time: float = Field(..., description="Total speaking time in seconds")

class SpeakerJobCreate(BaseModel):
    job_type: SpeakerJobType
    num_speakers: Optional[int] = Field(None, ge=1, le=20, description="Optional: number of speakers to detect")
    parameters: Optional[Dict] = Field(None, description="Additional processing parameters")

    class Config:
        json_schema_extra = {
            "example": {
                "job_type": "diarization",
                "num_speakers": 3,
                "parameters": {
                    "min_speakers": 1,
                    "max_speakers": 5
                }
            }
        }

class SpeakerJobResponse(BaseModel):
    id: int
    job_type: SpeakerJobType
    status: ProcessingStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    task_id: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True

class DiarizationResult(BaseModel):
    speakers: List[SpeakerInfo]
    timeline: List[SpeakerSegment]
    rttm_path: str = Field(..., description="Path to RTTM file")
    num_speakers: int = Field(..., description="Total number of speakers detected")

    class Config:
        json_schema_extra = {
            "example": {
                "speakers": [
                    {
                        "label": "SPEAKER_00",
                        "total_speaking_time": 120.5
                    }
                ],
                "timeline": [
                    {
                        "start": 0.0,
                        "end": 5.2,
                        "speaker": "SPEAKER_00"
                    }
                ],
                "rttm_path": "processed/123/diarization.rttm",
                "num_speakers": 3
            }
        }

class ExtractionResult(BaseModel):
    num_speakers: int = Field(..., description="Number of speakers extracted")
    audio_files: List[Dict[str, str]] = Field(..., description="List of extracted audio files")
    rttm_path: str = Field(..., description="Path to RTTM file")
    speaker_stats: Optional[List[SpeakerInfo]] = Field(None, description="Optional speaker statistics")

    class Config:
        json_schema_extra = {
            "example": {
                "num_speakers": 3,
                "audio_files": [
                    {
                        "speaker": "SPEAKER_00",
                        "path": "processed/123/speaker_0.wav"
                    }
                ],
                "rttm_path": "processed/123/extraction.rttm",
                "speaker_stats": [
                    {
                        "label": "SPEAKER_00",
                        "total_speaking_time": 120.5
                    }
                ]
            }
        }

class SpeakerAnalysisMetrics(BaseModel):
    """Optional metrics for speaker analysis results"""
    confidence_scores: Dict[str, float] = Field(..., description="Confidence scores per speaker")
    overlap_ratio: float = Field(..., ge=0, le=1, description="Speaker overlap ratio")
    noise_level: float = Field(..., ge=0, description="Background noise level in dB")
    signal_quality: Dict[str, float] = Field(..., description="Audio quality metrics")

    class Config:
        json_schema_extra = {
            "example": {
                "confidence_scores": {
                    "SPEAKER_00": 0.95,
                    "SPEAKER_01": 0.87
                },
                "overlap_ratio": 0.15,
                "noise_level": -45.3,
                "signal_quality": {
                    "snr": 25.4,
                    "clarity": 0.85
                }
            }
        } 
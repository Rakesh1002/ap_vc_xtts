from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

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

    # Add example for better API documentation
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
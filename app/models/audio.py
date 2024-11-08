from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base
from datetime import datetime
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

class BaseJob(Base):
    """Base class for all processing jobs"""
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    status = Column(SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING)
    task_id = Column(String, index=True, nullable=True)
    input_path = Column(String, nullable=False)
    error_message = Column(String, nullable=True)
    parameters = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

class Voice(Base):
    """Model for voice profiles"""
    __tablename__ = "voices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    cloning_jobs = relationship("CloningJob", back_populates="voice")

class CloningJob(BaseJob):
    """Model for voice cloning jobs"""
    __tablename__ = "cloning_jobs"

    voice_id = Column(Integer, ForeignKey("voices.id"))
    input_text = Column(String, nullable=False)
    output_path = Column(String, nullable=True)

    # Relationships
    voice = relationship("Voice", back_populates="cloning_jobs")

class TranslationJob(BaseJob):
    """Model for translation jobs"""
    __tablename__ = "translation_jobs"

    source_language = Column(String, nullable=True)
    target_language = Column(String, nullable=False)
    transcript_path = Column(String, nullable=True)
    audio_output_path = Column(String, nullable=True)

class SpeakerJob(BaseJob):
    """Model for speaker diarization and extraction jobs"""
    __tablename__ = "speaker_jobs"

    job_type = Column(SQLEnum(JobType), nullable=False)
    num_speakers = Column(Integer, nullable=True)
    rttm_path = Column(String, nullable=True)
    output_paths = Column(JSON, nullable=True)  # List of output audio file paths

    @property
    def is_diarization(self):
        return self.job_type == JobType.SPEAKER_DIARIZATION
    
    @property
    def is_extraction(self):
        return self.job_type == JobType.SPEAKER_EXTRACTION
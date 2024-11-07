from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum
from datetime import datetime

class ProcessingStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class BaseJob(Base):
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    task_id = Column(String, nullable=True)
    queue = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

class Voice(Base):
    __tablename__ = "voices"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    cloning_jobs = relationship("CloningJob", back_populates="voice")

class CloningJob(BaseJob):
    __tablename__ = "cloning_jobs"
    
    voice_id = Column(Integer, ForeignKey("voices.id"))
    input_text = Column(String, nullable=False)
    output_path = Column(String)
    
    # Relationships
    voice = relationship("Voice", back_populates="cloning_jobs")

class TranslationJob(BaseJob):
    __tablename__ = "translation_jobs"
    
    source_language = Column(String)
    target_language = Column(String, nullable=False)
    input_path = Column(String, nullable=False)
    transcript_path = Column(String)
    audio_output_path = Column(String)
    
    # Remove the incorrect relationship with Voice
    # TranslationJob doesn't need a relationship with Voice
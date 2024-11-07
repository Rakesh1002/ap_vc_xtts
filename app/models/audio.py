from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class ProcessingStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Voice(Base):
    __tablename__ = "voices"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    cloning_jobs = relationship("CloningJob", back_populates="voice")

class CloningJob(Base):
    __tablename__ = "cloning_jobs"
    
    id = Column(Integer, primary_key=True)
    voice_id = Column(Integer, ForeignKey("voices.id"))
    status = Column(Enum(ProcessingStatus), nullable=False)
    input_text = Column(String, nullable=False)
    output_path = Column(String)
    created_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    voice = relationship("Voice", back_populates="cloning_jobs")

class TranslationJob(Base):
    __tablename__ = "translation_jobs"
    
    id = Column(Integer, primary_key=True)
    status = Column(Enum(ProcessingStatus), nullable=False)
    source_language = Column(String)
    target_language = Column(String, nullable=False)
    input_path = Column(String, nullable=False)
    transcript_path = Column(String)
    audio_output_path = Column(String)
    created_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True)) 
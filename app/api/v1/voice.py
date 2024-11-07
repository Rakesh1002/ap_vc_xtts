from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.audio import VoiceCreate, Voice, CloningJobCreate, CloningJob
from app.models.audio import Voice as VoiceModel, CloningJob as CloningJobModel, ProcessingStatus
from app.services.voice_cloning import VoiceCloningService
from datetime import datetime
import uuid
from typing import List
from app.core.errors import AudioProcessingError, ErrorCodes
from app.core.constants import MAX_AUDIO_SIZE, SUPPORTED_AUDIO_FORMATS
from app.services.storage_service import StorageService

router = APIRouter()
voice_service = VoiceCloningService()
storage_service = StorageService()  # Use StorageService

@router.post("/voices/", response_model=Voice)
async def create_voice(
    name: str = Form(...),  # Ensure this is defined as a form field
    description: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Validate audio format
        if file.content_type not in SUPPORTED_AUDIO_FORMATS:
            raise AudioProcessingError(
                message="Unsupported audio format",
                error_code=ErrorCodes.INVALID_AUDIO_FORMAT,
                details={"supported_formats": list(SUPPORTED_AUDIO_FORMATS)}
            )
        
        # Validate file size
        file_size = 0
        chunk_size = 8192  # 8KB chunks
        
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > MAX_AUDIO_SIZE:
                raise AudioProcessingError(
                    message="File too large",
                    error_code=ErrorCodes.FILE_TOO_LARGE,
                    details={"max_size_mb": MAX_AUDIO_SIZE / (1024 * 1024)}
                )
        
        await file.seek(0)  # Reset file pointer
        
        # Generate S3 path
        file_path = f"voices/{uuid.uuid4()}/{file.filename}"
        
        # Upload to S3 using StorageService
        try:
            await storage_service.upload_file(file.file, file_path)
        except Exception as e:
            raise AudioProcessingError(
                message="Failed to upload file",
                error_code=ErrorCodes.UPLOAD_FAILED,
                original_error=e
            )
        
        # Create voice record
        voice = VoiceModel(
            name=name,
            description=description,
            file_path=file_path,
            created_at=datetime.utcnow()
        )
        
        db.add(voice)
        await db.commit()
        await db.refresh(voice)
        
        return voice
        
    except AudioProcessingError as e:
        raise HTTPException(
            status_code=400,
            detail=e.to_dict()
        )
    except Exception as e:
        logger.exception("Unexpected error in create_voice")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@router.post("/clone/", response_model=CloningJob)
async def create_cloning_job(
    job: CloningJobCreate,
    db: AsyncSession = Depends(get_db)
):
    # Check if voice exists
    voice_result = await db.execute(
        select(VoiceModel).where(VoiceModel.id == job.voice_id)
    )
    voice = voice_result.scalar_one_or_none()
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")
    
    # Create job record
    cloning_job = CloningJobModel(
        voice_id=job.voice_id,
        input_text=job.input_text,
        status=ProcessingStatus.PENDING,
        created_at=datetime.utcnow()
    )
    
    db.add(cloning_job)
    await db.commit()
    await db.refresh(cloning_job)
    
    # Start Celery task
    clone_voice.delay(cloning_job.id)
    
    return cloning_job

@router.get("/voices/", response_model=List[Voice])
async def list_voices(
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(VoiceModel).offset(skip).limit(limit)
    )
    voices = result.scalars().all()
    return voices 

@router.get("/clone/{job_id}", response_model=CloningJob)
async def get_cloning_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CloningJobModel).where(CloningJobModel.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Cloning job not found")
    
    return job
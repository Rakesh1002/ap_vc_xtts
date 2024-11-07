from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.audio import TranslationJobCreate, TranslationJob
from app.models.audio import TranslationJob as TranslationJobModel, ProcessingStatus
from app.workers.translation_tasks import translate_audio
from datetime import datetime
import uuid
from typing import List, Optional
from sqlalchemy import select
from app.services.translation import TranslationService
from app.services.media_extractor import MediaExtractor
from pathlib import Path
from app.core.errors import AudioProcessingError
import logging
from app.core.constants import CeleryQueues, CeleryTasks
from app.core.celery_app import celery_app

router = APIRouter()
translation_service = TranslationService()

SUPPORTED_LANGUAGES = {"en", "es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko"}

logger = logging.getLogger(__name__)

@router.post("/translate/", response_model=TranslationJob)
async def create_translation_job(
    target_language: str,
    source_language: str | None = None,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Validate languages
        if target_language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported target language. Supported languages: {', '.join(SUPPORTED_LANGUAGES)}"
            )
        if source_language and source_language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported source language. Supported languages: {', '.join(SUPPORTED_LANGUAGES)}"
            )
        
        # Validate audio file
        if not file.content_type.startswith('audio/'):
            raise HTTPException(status_code=400, detail="File must be an audio file")
        
        # Generate S3 path
        file_path = f"translations/inputs/{uuid.uuid4()}/{file.filename}"
        
        # Upload to S3
        try:
            translation_service._upload_to_s3(file.file, file_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to upload file")
        
        # Create job record
        translation_job = TranslationJobModel(
            status=ProcessingStatus.PENDING,
            source_language=source_language,
            target_language=target_language,
            input_path=file_path,
            created_at=datetime.utcnow(),
            queue=CeleryQueues.TRANSLATION
        )
        
        db.add(translation_job)
        await db.commit()
        await db.refresh(translation_job)
        
        # Start Celery task with translation queue
        logger.debug(f"Starting translation job: {translation_job.id} in queue: {CeleryQueues.TRANSLATION}")
        task = celery_app.send_task(
            CeleryTasks.TRANSLATE_AUDIO,
            args=[translation_job.id],
            queue=CeleryQueues.TRANSLATION,
            priority=0
        )
        
        translation_job.task_id = task.id
        await db.commit()
        
        return translation_job
    except Exception as e:
        logger.error(f"Failed to process file {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process file")

@router.get("/translations/", response_model=List[TranslationJob])
async def list_translations(
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TranslationJobModel)
        .offset(skip)
        .limit(limit)
        .order_by(TranslationJobModel.created_at.desc())
    )
    translations = result.scalars().all()
    return translations

@router.get("/translations/{job_id}", response_model=TranslationJob)
async def get_translation(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TranslationJobModel).where(TranslationJobModel.id == job_id)
    )
    translation = result.scalar_one_or_none()
    
    if not translation:
        raise HTTPException(status_code=404, detail="Translation job not found")
    
    return translation

# Add new endpoint for URL-based translation
@router.post("/translate/url/", response_model=TranslationJob)
async def create_translation_job_from_url(
    url: str,
    target_language: str,
    source_language: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    # Validate languages
    if target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target language. Supported languages: {', '.join(SUPPORTED_LANGUAGES)}"
        )
    
    # Extract audio from URL
    media_extractor = MediaExtractor()
    try:
        local_path, mime_type = await media_extractor.extract_audio(url)
    except AudioProcessingError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    
    # Upload to S3
    file_name = Path(local_path).name
    s3_path = f"translations/inputs/{uuid.uuid4()}/{file_name}"
    
    try:
        with open(local_path, 'rb') as f:
            translation_service._upload_to_s3(f, s3_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to upload file")
    finally:
        # Cleanup temporary file
        Path(local_path).unlink(missing_ok=True)
    
    # Create job record
    translation_job = TranslationJobModel(
        status=ProcessingStatus.PENDING,
        source_language=source_language,
        target_language=target_language,
        input_path=s3_path,
        created_at=datetime.utcnow(),
        queue=CeleryQueues.TRANSLATION
    )
    
    db.add(translation_job)
    await db.commit()
    await db.refresh(translation_job)
    
    # Start Celery task with translation queue
    logger.debug(f"Starting translation job: {translation_job.id} in queue: {CeleryQueues.TRANSLATION}")
    task = celery_app.send_task(
        CeleryTasks.TRANSLATE_AUDIO,
        args=[translation_job.id],
        queue=CeleryQueues.TRANSLATION,
        priority=0
    )
    
    translation_job.task_id = task.id
    await db.commit()
    
    return translation_job

@router.post("/translate/batch/", response_model=List[TranslationJob])
async def create_batch_translation_jobs(
    files: List[UploadFile] = File(...),
    target_language: str = Form(...),
    source_language: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    jobs = []
    
    for file in files:
        try:
            # Create individual job
            job = await create_translation_job(
                target_language=target_language,
                source_language=source_language,
                file=file,
                db=db
            )
            jobs.append(job)
        except Exception as e:
            logger.error(f"Failed to process file {file.filename}: {str(e)}")
            continue
    
    if not jobs:
        raise HTTPException(
            status_code=400,
            detail="No files were successfully processed"
        )
    
    return jobs
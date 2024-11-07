from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.schemas.audio import VoiceCreate, Voice, CloningJobCreate, CloningJob
from app.models.audio import Voice as VoiceModel, CloningJob as CloningJobModel, ProcessingStatus
from app.services.voice_cloning import VoiceCloningService
from datetime import datetime
import uuid
from typing import List
from app.core.errors import AudioProcessingError, ErrorCodes
from app.core.constants import MAX_AUDIO_SIZE, SUPPORTED_AUDIO_FORMATS, CeleryQueues, CeleryTasks
from app.services.storage_service import StorageService
from app.core.celery_app import celery_app
import os
import logging
from celery.result import AsyncResult
from celery import chain
from sqlalchemy import and_
from datetime import timedelta
from app.core.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
storage_service = StorageService()
settings = get_settings()

# Define the Celery task name
CLONE_VOICE_TASK = "app.workers.voice_tasks.clone_voice"

# Add dependency
async def get_voice_service():
    service = VoiceCloningService()
    try:
        yield service
    finally:
        # Cleanup if needed
        pass

@router.post("/voices/", response_model=Voice)
async def create_voice(
    name: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Create a new voice profile from an audio file"""
    try:
        # Validate audio format
        if file.content_type not in SUPPORTED_AUDIO_FORMATS:
            raise AudioProcessingError(
                message="Unsupported audio format",
                error_code=ErrorCodes.INVALID_AUDIO_FORMAT,
                details={"supported_formats": list(SUPPORTED_AUDIO_FORMATS)}
            )
        
        # Validate file size before upload
        file_size = file.file.seek(0, os.SEEK_END)
        file.file.seek(0)  # Reset file pointer
        
        if file_size > MAX_AUDIO_SIZE:
            raise AudioProcessingError(
                message="File too large",
                error_code=ErrorCodes.FILE_TOO_LARGE,
                details={"max_size_mb": MAX_AUDIO_SIZE / (1024 * 1024)}
            )
        
        # Generate S3 path with sanitized filename
        safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
        file_path = f"voices/{uuid.uuid4()}/{safe_filename}"
        
        try:
            logger.debug(f"Uploading file to path: {file_path}")
            await storage_service.upload_file(file.file, file_path)
        except Exception as e:
            logger.error(f"Failed to upload file: {str(e)}")
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
        
        logger.info(f"Successfully created voice profile: {voice.id}")
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
    db: AsyncSession = Depends(get_db),
    voice_service: VoiceCloningService = Depends(get_voice_service)
):
    """Create a new voice cloning job"""
    try:
        # Check if voice exists
        voice_result = await db.execute(
            select(VoiceModel).where(VoiceModel.id == job.voice_id)
        )
        voice = voice_result.scalar_one_or_none()
        if not voice:
            raise HTTPException(status_code=404, detail="Voice not found")
        
        # Validate text length
        if len(job.input_text) > 5000:
            raise HTTPException(status_code=400, detail="Text too long (max 5000 characters)")
        
        # Create job record with queue information
        cloning_job = CloningJobModel(
            voice_id=job.voice_id,
            input_text=job.input_text,
            status=ProcessingStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            queue=CeleryQueues.VOICE
        )
        
        db.add(cloning_job)
        await db.commit()
        await db.refresh(cloning_job)
        
        # Start Celery task with voice queue
        logger.debug(f"Starting cloning job: {cloning_job.id} in queue: {CeleryQueues.VOICE}")
        task = celery_app.send_task(
            CeleryTasks.CLONE_VOICE,
            args=[cloning_job.id],
            queue=CeleryQueues.VOICE,
            priority=0
        )
        
        # Store task ID
        cloning_job.task_id = task.id
        await db.commit()
        
        return cloning_job
        
    except Exception as e:
        logger.exception("Error creating cloning job")
        raise HTTPException(
            status_code=500,
            detail="Failed to create cloning job"
        )

@router.get("/clone/{job_id}/status", response_model=dict)
async def get_cloning_job_status(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed status of a cloning job"""
    try:
        result = await db.execute(
            select(CloningJobModel).where(CloningJobModel.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=404, detail="Cloning job not found")
            
        # Get Celery task status if task_id exists
        task_status = None
        if job.task_id:
            task_result = AsyncResult(job.task_id)
            
            # Handle different task states and info types
            progress = 0
            if task_result.state == 'PROGRESS' and isinstance(task_result.info, dict):
                progress = task_result.info.get('progress', 0)
            elif task_result.state == 'SUCCESS':
                progress = 100
                
            task_status = {
                'state': task_result.state,
                'progress': progress,
                'error': str(task_result.result) if task_result.failed() else None
            }
        
        # Generate presigned S3 URL if output exists
        output_url = None
        if job.output_path:
            output_url = storage_service.generate_presigned_url(
                job.output_path,
                expiration=3600  # URL valid for 1 hour
            )
        
        return {
            'job_id': job.id,
            'status': job.status.value,
            'created_at': job.created_at,
            'updated_at': job.updated_at,
            'completed_at': job.completed_at,
            'task_status': task_status,
            'output_path': job.output_path,
            'output_url': output_url,  # Presigned URL
            'error_message': job.error_message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving cloning job status {job_id}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve job status"
        )

@router.get("/voices/", response_model=List[Voice])
async def list_voices(
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """List all voice profiles with pagination"""
    try:
        result = await db.execute(
            select(VoiceModel)
            .order_by(VoiceModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        voices = result.scalars().all()
        return voices
    except Exception as e:
        logger.exception("Error listing voices")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve voices"
        )

@router.post("/clone/{job_id}/retry", response_model=dict)
async def retry_cloning_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Manually retry a failed or pending job"""
    try:
        # Get job
        result = await db.execute(
            select(CloningJobModel).where(CloningJobModel.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Only retry failed or stuck jobs
        if job.status not in [ProcessingStatus.FAILED, ProcessingStatus.PENDING]:
            raise HTTPException(
                status_code=400,
                detail="Can only retry failed or pending jobs"
            )
        
        # Reset job status
        job.status = ProcessingStatus.PENDING
        job.error_message = None
        job.updated_at = datetime.utcnow()
        
        # Start new task
        task = celery_app.send_task(
            CeleryTasks.CLONE_VOICE,
            args=[job_id],
            queue=CeleryQueues.VOICE
        )
        
        # Update task ID
        job.task_id = task.id
        await db.commit()
        
        return {
            "message": "Retry initiated",
            "task_id": task.id,
            "job_id": job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrying job {job_id}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retry job"
        )

@router.post("/clone/retry-all", response_model=dict)
async def retry_failed_jobs(
    db: AsyncSession = Depends(get_db),
    max_age_hours: int = 24
):
    """Retry all failed or stuck jobs within the age limit"""
    try:
        # Find failed and stuck jobs
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        result = await db.execute(
            select(CloningJobModel).where(
                and_(
                    CloningJobModel.status.in_([ProcessingStatus.FAILED, ProcessingStatus.PENDING]),
                    CloningJobModel.created_at >= cutoff_time
                )
            )
        )
        jobs = result.scalars().all()
        
        retried_count = 0
        for job in jobs:
            try:
                # Reset job status
                job.status = ProcessingStatus.PENDING
                job.error_message = None
                job.updated_at = datetime.utcnow()
                
                # Start new task
                task = celery_app.send_task(
                    CeleryTasks.CLONE_VOICE,
                    args=[job.id],
                    queue=CeleryQueues.VOICE
                )
                
                # Update task ID
                job.task_id = task.id
                retried_count += 1
                
            except Exception as e:
                logger.error(f"Failed to retry job {job.id}: {str(e)}")
                continue
        
        await db.commit()
        
        return {
            "message": f"Retried {retried_count} jobs",
            "retried_count": retried_count,
            "total_jobs": len(jobs)
        }
        
    except Exception as e:
        logger.exception("Error retrying failed jobs")
        raise HTTPException(
            status_code=500,
            detail="Failed to retry jobs"
        )
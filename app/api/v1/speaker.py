from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.celery_app import celery_app
from app.services.storage_service import StorageService
from app.core.constants import CeleryTasks, CeleryQueues
from app.models.audio import SpeakerJob, JobType, ProcessingStatus
from app.schemas.speaker import (
    SpeakerJobCreate, 
    SpeakerJobResponse, 
    SpeakerJobType,
    DiarizationResult,
    ExtractionResult
)
from datetime import datetime
import uuid
import logging
from typing import Optional, List
from app.core.errors import AudioProcessingError, ErrorCodes

router = APIRouter()
logger = logging.getLogger(__name__)
storage_service = StorageService()

@router.post("/diarize", response_model=SpeakerJobResponse)
async def create_diarization_job(
    file: UploadFile = File(...),
    num_speakers: Optional[int] = Query(None, description="Optional: specify number of speakers"),
    db: AsyncSession = Depends(get_db)
):
    """Create a speaker diarization job"""
    return await _create_speaker_job(
        file=file,
        job_type=SpeakerJobType.DIARIZATION,
        num_speakers=num_speakers,
        db=db
    )

@router.post("/extract", response_model=SpeakerJobResponse)
async def create_extraction_job(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Create a speaker extraction job"""
    return await _create_speaker_job(
        file=file,
        job_type=SpeakerJobType.EXTRACTION,
        db=db
    )

async def _create_speaker_job(
    file: UploadFile,
    job_type: SpeakerJobType,
    num_speakers: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
) -> SpeakerJobResponse:
    try:
        # Validate file type
        if not file.content_type.startswith('audio/'):
            raise AudioProcessingError(
                message="Invalid file type. Must be audio file.",
                error_code=ErrorCodes.INVALID_AUDIO_FORMAT
            )

        # Generate unique file path
        file_id = str(uuid.uuid4())
        file_path = f"uploads/speaker_{job_type.value}/{file_id}/{file.filename}"
        
        # Upload file
        file_content = await file.read()
        await storage_service.upload_file(
            file_content,
            file_path
        )
        
        # Map SpeakerJobType to JobType
        job_type_map = {
            SpeakerJobType.DIARIZATION: JobType.SPEAKER_DIARIZATION,
            SpeakerJobType.EXTRACTION: JobType.SPEAKER_EXTRACTION
        }
        
        # Create job record
        job = SpeakerJob(
            job_type=job_type_map[job_type],
            status=ProcessingStatus.PENDING,
            input_path=file_path,
            num_speakers=num_speakers,
            created_at=datetime.utcnow()
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        # Start Celery task
        task_name = (CeleryTasks.DIARIZE_SPEAKERS if job_type == SpeakerJobType.DIARIZATION 
                    else CeleryTasks.EXTRACT_SPEAKERS)
        
        task = celery_app.send_task(
            task_name,
            args=[job.id, num_speakers] if num_speakers else [job.id],
            queue=CeleryQueues.SPEAKER
        )
        
        # Update job with task ID
        job.task_id = task.id
        await db.commit()
        
        return SpeakerJobResponse(
            id=job.id,
            job_type=job_type,
            status=ProcessingStatus.PROCESSING,
            created_at=job.created_at,
            task_id=task.id
        )
        
    except AudioProcessingError as e:
        logger.error(f"Failed to create {job_type.value} job: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(f"Failed to create {job_type.value} job: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process {job_type.value} request"
        )

@router.get("/jobs/{job_id}", response_model=SpeakerJobResponse)
async def get_speaker_job_status(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get status and results of a speaker analysis job"""
    job = await db.get(SpeakerJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Map JobType back to SpeakerJobType
    job_type_map = {
        JobType.SPEAKER_DIARIZATION: SpeakerJobType.DIARIZATION,
        JobType.SPEAKER_EXTRACTION: SpeakerJobType.EXTRACTION
    }
    
    # Create response with base job info
    response = {
        "id": job.id,
        "job_type": job_type_map[job.job_type],
        "status": job.status,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "result": job.result,
        "error": job.error_message
    }
    
    # Generate pre-signed URLs for completed jobs with results
    if job.status == ProcessingStatus.COMPLETED and job.result:
        try:
            # Create a deep copy of the result to avoid modifying the original
            result = dict(job.result)
            
            # Handle file URLs
            if "files" in result:
                for file in result["files"]:
                    if "path" in file and isinstance(file["path"], str):
                        try:
                            file["download_url"] = await storage_service.get_presigned_url(
                                file["path"],
                                expiration=3600  # 1 hour expiration
                            )
                        except AudioProcessingError as e:
                            logger.warning(f"Failed to generate URL for file {file['path']}: {str(e)}")
                            file["download_url"] = None
            
            # Handle speaker audio URLs
            if "speakers" in result:
                for speaker in result["speakers"]:
                    if "audio_path" in speaker and isinstance(speaker["audio_path"], str):
                        try:
                            speaker["download_url"] = await storage_service.get_presigned_url(
                                speaker["audio_path"],
                                expiration=3600  # 1 hour expiration
                            )
                        except AudioProcessingError as e:
                            logger.warning(f"Failed to generate URL for speaker audio {speaker['audio_path']}: {str(e)}")
                            speaker["download_url"] = None
            
            response["result"] = result
            
        except Exception as e:
            logger.error(f"Error generating pre-signed URLs for job {job_id}: {str(e)}")
            # Don't fail the request if URL generation fails
            # Just return the results without URLs
    
    return SpeakerJobResponse(**response)

@router.get("/jobs", response_model=List[SpeakerJobResponse])
async def list_speaker_jobs(
    job_type: Optional[SpeakerJobType] = None,
    status: Optional[ProcessingStatus] = None,
    limit: int = Query(10, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List speaker analysis jobs with optional filtering"""
    try:
        # Build base query
        query = (
            select(SpeakerJob)
            .order_by(SpeakerJob.created_at.desc())  # Order by newest first
        )
        
        # Apply filters
        if job_type:
            job_type_map = {
                SpeakerJobType.DIARIZATION: JobType.SPEAKER_DIARIZATION,
                SpeakerJobType.EXTRACTION: JobType.SPEAKER_EXTRACTION
            }
            query = query.filter(SpeakerJob.job_type == job_type_map[job_type])
        if status:
            query = query.filter(SpeakerJob.status == status)
        
        # Add pagination
        query = query.offset(offset).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        # Map results and generate URLs for completed jobs
        job_type_map = {
            JobType.SPEAKER_DIARIZATION: SpeakerJobType.DIARIZATION,
            JobType.SPEAKER_EXTRACTION: SpeakerJobType.EXTRACTION
        }
        
        responses = []
        for job in jobs:
            response = {
                "id": job.id,
                "job_type": job_type_map[job.job_type],
                "status": job.status,
                "created_at": job.created_at,
                "completed_at": job.completed_at,
                "result": job.result,
                "error": job.error_message
            }
            
            # Generate URLs for completed jobs
            if job.status == ProcessingStatus.COMPLETED and job.result:
                try:
                    result = dict(job.result)
                    
                    if "files" in result:
                        for file in result["files"]:
                            if "path" in file and isinstance(file["path"], str):
                                try:
                                    file["download_url"] = await storage_service.get_presigned_url(
                                        file["path"],
                                        expiration=3600  # 1 hour expiration
                                    )
                                except AudioProcessingError as e:
                                    logger.warning(f"Failed to generate URL for file {file['path']}: {str(e)}")
                                    file["download_url"] = None
                                    
                    if "speakers" in result:
                        for speaker in result["speakers"]:
                            if "audio_path" in speaker and isinstance(speaker["audio_path"], str):
                                try:
                                    speaker["download_url"] = await storage_service.get_presigned_url(
                                        speaker["audio_path"],
                                        expiration=3600  # 1 hour expiration
                                    )
                                except AudioProcessingError as e:
                                    logger.warning(f"Failed to generate URL for speaker audio {speaker['audio_path']}: {str(e)}")
                                    speaker["download_url"] = None
                                    
                    response["result"] = result
                    
                except Exception as e:
                    logger.error(f"Error generating pre-signed URLs for job {job.id}: {str(e)}")
                    # Don't fail the request if URL generation fails
                    
            responses.append(SpeakerJobResponse(**response))
        
        return responses
        
    except Exception as e:
        logger.error(f"Error listing speaker jobs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list speaker jobs"
        )
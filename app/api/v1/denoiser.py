from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Optional, List
import tempfile
from pathlib import Path
from datetime import datetime
import logging
import os

from app.core.config import get_settings
from app.services.denoiser_service import DenoiserService
from app.services.storage_service import StorageService
from app.schemas.audio import DenoiseRequest, DenoiseResponse, DenoiseJob
from app.core.errors import AudioProcessingError
from app.db.session import AsyncSessionLocal, get_db
from app.models.audio import DenoiseJob as DenoiseJobModel, ProcessingStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.celery_app import celery_app
from app.core.constants import CeleryTasks, CeleryQueues
from app.services.spectral_denoiser_service import NoiseType
import torch
from app.core.errors import DenoiserError, ErrorCodes, ErrorSeverity
from app.core.constants import MAX_AUDIO_SIZE, SUPPORTED_AUDIO_EXTENSIONS, SUPPORTED_AUDIO_FORMATS

router = APIRouter()
settings = get_settings()
denoiser_service = DenoiserService()
storage_service = StorageService()
logger = logging.getLogger(__name__)

@router.post("/denoise", response_model=DenoiseJob)
async def create_denoise_job(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Create a new audio denoising job"""
    
    try:
        # Check if denoiser service is initialized
        if not denoiser_service.initialized:
            raise DenoiserError(
                message="Denoiser service is not initialized",
                error_code=ErrorCodes.DENOISER_NOT_INITIALIZED,
                severity=ErrorSeverity.CRITICAL
            )
        
        # Validate file format and extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in SUPPORTED_AUDIO_EXTENSIONS:
            raise AudioProcessingError(
                message=f"Unsupported file extension: {file_ext}",
                error_code=ErrorCodes.UNSUPPORTED_AUDIO_FORMAT,
                details={
                    "extension": file_ext,
                    "supported_extensions": list(SUPPORTED_AUDIO_EXTENSIONS)
                },
                severity=ErrorSeverity.MEDIUM
            )

        if file.content_type not in SUPPORTED_AUDIO_FORMATS:
            raise AudioProcessingError(
                message=f"Unsupported content type: {file.content_type}",
                error_code=ErrorCodes.UNSUPPORTED_AUDIO_FORMAT,
                details={
                    "content_type": file.content_type,
                    "supported_formats": list(SUPPORTED_AUDIO_FORMATS)
                },
                severity=ErrorSeverity.MEDIUM
            )

        # Create temporary file and validate
        temp_file = None
        try:
            # Check file size before reading
            content = await file.read()
            if len(content) > MAX_AUDIO_SIZE:
                raise AudioProcessingError(
                    message="File size exceeds maximum limit",
                    error_code=ErrorCodes.FILE_TOO_LARGE,
                    details={
                        "max_size": MAX_AUDIO_SIZE,
                        "file_size": len(content)
                    }
                )

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
            temp_file.write(content)
            temp_file.flush()
            
            # Validate audio file
            try:
                audio_info = denoiser_service.validate_audio_file(temp_file.name)
            except DenoiserError as e:
                raise HTTPException(
                    status_code=400,
                    detail=e.to_dict()
                )
            
            # Upload file to S3
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            input_key = f"uploads/denoiser/{timestamp}_{file.filename}"
            
            try:
                await storage_service.upload_file(
                    temp_file.name,
                    input_key
                )
            except Exception as e:
                raise AudioProcessingError(
                    message="Failed to upload file",
                    error_code=ErrorCodes.UPLOAD_FAILED,
                    details={"error": str(e)},
                    original_error=e
                )
            
            # Create job record
            try:
                # Create job with proper defaults
                job = DenoiseJobModel(
                    input_path=input_key,
                    status=ProcessingStatus.PENDING,
                    parameters={
                        "audio_info": audio_info,
                        "original_filename": file.filename
                    },
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                # Add and flush to get the ID
                db.add(job)
                await db.flush()
                
                # Start celery task
                try:
                    task = celery_app.send_task(
                        CeleryTasks.DENOISE_AUDIO,
                        args=[job.id],
                        queue=CeleryQueues.DENOISER
                    )
                    
                    # Update task ID
                    job.task_id = task.id
                    await db.commit()
                    await db.refresh(job)
                    
                    return job
                    
                except Exception as e:
                    await db.rollback()
                    raise AudioProcessingError(
                        message="Failed to start processing task",
                        error_code=ErrorCodes.TASK_CREATION_FAILED,
                        details={"error": str(e)},
                        original_error=e
                    )
                    
            except Exception as e:
                await db.rollback()
                logger.error(f"Database error creating job: {str(e)}")
                raise AudioProcessingError(
                    message="Failed to create job record",
                    error_code=ErrorCodes.DATABASE_ERROR,
                    details={"error": str(e)},
                    original_error=e
                )
            
        finally:
            if temp_file:
                try:
                    temp_file.close()
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file: {e}")
                    
    except (AudioProcessingError, DenoiserError) as e:
        logger.error(f"Audio processing error: {str(e)}")
        raise HTTPException(
            status_code=400 if e.error_code in [
                ErrorCodes.INVALID_AUDIO_FORMAT,
                ErrorCodes.UNSUPPORTED_AUDIO_FORMAT,
                ErrorCodes.FILE_TOO_LARGE,
                ErrorCodes.AUDIO_TOO_LONG,
                ErrorCodes.AUDIO_TOO_SHORT
            ] else 500,
            detail=e.to_dict()
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": ErrorCodes.UNKNOWN_ERROR,
                "message": "An unexpected error occurred",
                "details": str(e)
            }
        )

@router.get("/jobs/{job_id}", response_model=DenoiseJob)
async def get_denoise_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get status of a denoising job"""
    # Get job using select to ensure we get all fields
    result = await db.execute(
        select(DenoiseJobModel).where(DenoiseJobModel.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    # Convert job to dict for response
    response_data = {
        "id": job.id,
        "status": job.status,
        "input_path": job.input_path,
        "output_path": job.output_path,
        "task_id": job.task_id,
        "error_message": job.error_message,
        "stats": job.stats,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "completed_at": job.completed_at,
        "output_url": None  # Default to None
    }
    
    # Generate presigned URL if job is completed and has output
    if job.status == ProcessingStatus.COMPLETED and job.output_path:
        try:
            storage_service = StorageService()
            response_data['output_url'] = await storage_service.get_presigned_url(
                key=job.output_path,
                expiration=3600  # 1 hour
            )
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for job {job_id}: {e}")
            # Keep output_url as None if URL generation fails
    
    return response_data

@router.get("/jobs", response_model=List[DenoiseJob])
async def list_denoise_jobs(
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """List all denoising jobs"""
    result = await db.execute(
        select(DenoiseJobModel)
        .order_by(DenoiseJobModel.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    jobs = result.scalars().all()
    
    # Generate presigned URLs for completed jobs
    response_jobs = []
    for job in jobs:
        job_data = job.__dict__
        if job.status == ProcessingStatus.COMPLETED and job.output_path:
            try:
                presigned_url = await storage_service.get_presigned_url(
                    job.output_path,
                    expiry=3600
                )
                job_data['output_url'] = presigned_url
            except Exception as e:
                logger.error(f"Failed to generate presigned URL for job {job.id}: {e}")
                job_data['output_url'] = None
        else:
            job_data['output_url'] = None
        response_jobs.append(job_data)
        
    return response_jobs

@router.get("/health")
async def check_denoiser_health():
    """Check if the denoising service is available"""
    try:
        if not denoiser_service.initialized:
            return {
                "status": "unavailable",
                "error": "Denoiser service not initialized"
            }
            
        return {
            "status": "available",
            "device": denoiser_service.device,
            "model": "facebook_dns64",
            "cuda_available": torch.cuda.is_available(),
            "cuda_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

# Add new endpoints for spectral denoising
@router.post("/spectral/denoise", response_model=DenoiseJob)
async def create_spectral_denoise_job(
    file: UploadFile = File(...),
    noise_type: NoiseType = NoiseType.GENERAL,
    prop_decrease: Optional[float] = None,
    time_constant_s: Optional[float] = None,
    freq_mask_smooth_hz: Optional[int] = None,
    time_mask_smooth_ms: Optional[int] = None,
    stationary: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """Create a new audio denoising job using spectral gating"""
    try:
        # Create temporary file to store upload
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix)
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
            
            # Upload to S3
            storage_service = StorageService()
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            input_key = f"uploads/spectral_denoiser/{timestamp}_{file.filename}"
            
            # Upload using file path instead of file object
            await storage_service.upload_file(temp_file.name, input_key)
            
            # Collect custom parameters if provided
            custom_params = {}
            if prop_decrease is not None:
                custom_params['prop_decrease'] = prop_decrease
            if time_constant_s is not None:
                custom_params['time_constant_s'] = time_constant_s
            if freq_mask_smooth_hz is not None:
                custom_params['freq_mask_smooth_hz'] = freq_mask_smooth_hz
            if time_mask_smooth_ms is not None:
                custom_params['time_mask_smooth_ms'] = time_mask_smooth_ms
            if stationary is not None:
                custom_params['stationary'] = stationary
            
            # Create job record
            job = DenoiseJobModel(
                input_path=input_key,
                status=ProcessingStatus.PENDING,
                parameters={
                    "noise_type": noise_type,
                    "custom_params": custom_params if custom_params else None
                }
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)

            # Start celery task
            task = celery_app.send_task(
                CeleryTasks.SPECTRAL_DENOISE_AUDIO,
                args=[job.id],
                queue=CeleryQueues.SPECTRAL
            )
            
            job.task_id = task.id
            await db.commit()
            await db.refresh(job)

            return DenoiseJob.model_validate(job)
            
        finally:
            if temp_file:
                try:
                    temp_file.close()
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file: {e}")
    
    except Exception as e:
        logger.error(f"Failed to create denoising job: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "JOB_CREATION_FAILED",
                "message": "Failed to create denoising job",
                "details": str(e)
            }
        )

@router.post("/jobs/{job_id}/retry", response_model=DenoiseJob)
async def retry_denoise_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Retry a failed denoising job"""
    # Get the job
    result = await db.execute(
        select(DenoiseJobModel).where(DenoiseJobModel.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
        
    # Check if job can be retried
    if job.status != ProcessingStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCodes.INVALID_STATE,
                "message": "Only failed jobs can be retried",
                "current_status": job.status
            }
        )
    
    try:
        # Update job status
        job.status = ProcessingStatus.PENDING
        job.error_message = None
        job.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(job)
        
        # Check parameters to determine which queue to use
        is_spectral = job.parameters and job.parameters.get("noise_type") is not None
        
        # Start new task based on parameters
        task = celery_app.send_task(
            CeleryTasks.SPECTRAL_DENOISE_AUDIO if is_spectral else CeleryTasks.DENOISE_AUDIO,
            args=[job.id],
            queue=CeleryQueues.SPECTRAL if is_spectral else CeleryQueues.DENOISER
        )
        
        # Update job with new task ID
        job.task_id = task.id
        await db.commit()
        await db.refresh(job)
        
        return job
        
    except Exception as e:
        logger.error(f"Failed to retry job {job_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": ErrorCodes.RETRY_FAILED,
                "message": "Failed to retry denoising job",
                "details": str(e)
            }
        )
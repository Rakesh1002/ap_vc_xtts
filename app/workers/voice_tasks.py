from app.core.celery_app import celery_app
from app.services.voice_cloning import VoiceCloningService
from app.models.audio import ProcessingStatus
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.models.audio import CloningJob
import logging
from datetime import datetime

@celery_app.task(name="clone_voice")
async def clone_voice(job_id: int):
    voice_service = VoiceCloningService()
    async with AsyncSessionLocal() as db:
        try:
            # Get job
            job = await db.execute(
                select(CloningJob).where(CloningJob.id == job_id)
            )
            job = job.scalar_one()
            
            # Update status to processing
            job.status = ProcessingStatus.PROCESSING
            await db.commit()
            
            # Process voice cloning
            output_path = await voice_service.clone_voice(
                voice_file_path=job.voice.file_path,
                text=job.input_text
            )
            
            # Update job with success
            job.status = ProcessingStatus.COMPLETED
            job.output_path = output_path
            job.completed_at = datetime.utcnow()
            await db.commit()
            
        except Exception as e:
            error_msg = f"Voice cloning failed for job {job_id}: {str(e)}"
            logging.error(error_msg)
            job.status = ProcessingStatus.FAILED
            job.completed_at = datetime.utcnow()
            await db.commit()
            raise Exception(error_msg)
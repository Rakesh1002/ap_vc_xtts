from app.core.celery_app import celery_app
from app.core.task_processor import task_processor
from app.core.constants import CeleryTasks, CeleryQueues
from app.services.voice_cloning import VoiceCloningService
from sqlalchemy import select
from app.models.audio import CloningJob, ProcessingStatus, Voice
from datetime import datetime
import logging
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Create synchronous engine and session factory for Celery tasks
engine = create_engine(settings.sync_database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@celery_app.task(
    name=CeleryTasks.CLONE_VOICE,
    queue=CeleryQueues.VOICE,
    bind=True,
    max_retries=3,
    soft_time_limit=3300,
    time_limit=3600
)
@task_processor.process_task("voice_cloning")
def clone_voice(self, job_id: int):
    """Voice cloning task"""
    voice_service = VoiceCloningService()
    
    # Use synchronous session
    with SessionLocal() as db:
        try:
            # Get job with voice relationship
            job = db.query(CloningJob).filter(CloningJob.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            # Get voice
            voice = db.query(Voice).filter(Voice.id == job.voice_id).first()
            if not voice:
                raise ValueError(f"Voice {job.voice_id} not found")
            
            # Update status to processing
            job.status = ProcessingStatus.PROCESSING
            job.updated_at = datetime.utcnow()
            db.commit()
            
            try:
                # Do voice cloning using sync version for Celery
                output_path = voice_service.clone_voice_sync(
                    voice_file_path=voice.file_path,
                    text=job.input_text,
                    progress_callback=lambda progress: self.update_state(
                        state='PROGRESS',
                        meta={'progress': progress}
                    )
                )
                
                # Update success status
                job.status = ProcessingStatus.COMPLETED
                job.output_path = output_path
                job.completed_at = datetime.utcnow()
                job.updated_at = datetime.utcnow()
                db.commit()
                
                logger.info(f"Successfully cloned voice for job {job_id}")
                return output_path
                
            except Exception as e:
                # Update failure status
                job.status = ProcessingStatus.FAILED
                job.error_message = str(e)
                job.updated_at = datetime.utcnow()
                db.commit()
                
                logger.error(f"Failed to clone voice for job {job_id}: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {str(e)}")
            db.rollback()
            raise
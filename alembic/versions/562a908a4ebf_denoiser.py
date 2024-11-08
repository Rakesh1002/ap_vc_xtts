"""denoiser

Revision ID: 562a908a4ebf
Revises: 863145be9d64
Create Date: 2024-11-09 02:15:47.596675

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '562a908a4ebf'
down_revision: Union[str, None] = '863145be9d64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create new enum type for processing status
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'processing_status_enum') THEN
                CREATE TYPE processing_status_enum AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_type_enum') THEN
                CREATE TYPE job_type_enum AS ENUM (
                    'VOICE_CLONING', 'TRANSLATION', 'SPEAKER_DIARIZATION', 
                    'SPEAKER_EXTRACTION', 'DENOISING'
                );
            END IF;
        END$$;
    """)

    # Drop the method column and its enum type
    op.execute("""
        ALTER TABLE denoise_jobs DROP COLUMN IF EXISTS method;
        DROP TYPE IF EXISTS denoisermethod;
    """)

    # Update existing data to use new enum types
    op.execute("""
        ALTER TABLE cloning_jobs 
        ALTER COLUMN status TYPE processing_status_enum 
        USING status::text::processing_status_enum;
        
        ALTER TABLE denoise_jobs 
        ALTER COLUMN status TYPE processing_status_enum 
        USING status::text::processing_status_enum;
        
        ALTER TABLE translation_jobs 
        ALTER COLUMN status TYPE processing_status_enum 
        USING status::text::processing_status_enum;
        
        ALTER TABLE speaker_jobs 
        ALTER COLUMN status TYPE processing_status_enum 
        USING status::text::processing_status_enum;
    """)

    # Update job type enum
    op.execute("""
        ALTER TABLE speaker_jobs 
        ALTER COLUMN job_type TYPE job_type_enum 
        USING job_type::text::job_type_enum;
    """)

    # Other column modifications
    op.alter_column('denoise_jobs', 'error_message',
               existing_type=sa.VARCHAR(),
               type_=sa.Text(),
               existing_nullable=True)
               
    op.alter_column('denoise_jobs', 'stats',
               existing_type=postgresql.JSON(),
               type_=postgresql.JSONB(),
               existing_nullable=True)
               
    op.alter_column('denoise_jobs', 'parameters',
               existing_type=postgresql.JSON(),
               type_=postgresql.JSONB(),
               existing_nullable=True)

def downgrade() -> None:
    # Create old enum types if they don't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'processingstatus') THEN
                CREATE TYPE processingstatus AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'jobtype') THEN
                CREATE TYPE jobtype AS ENUM (
                    'VOICE_CLONING', 'TRANSLATION', 'SPEAKER_DIARIZATION', 
                    'SPEAKER_EXTRACTION', 'DENOISING'
                );
            END IF;
        END$$;
    """)

    # Revert column types
    op.execute("""
        ALTER TABLE cloning_jobs 
        ALTER COLUMN status TYPE processingstatus 
        USING status::text::processingstatus;
        
        ALTER TABLE denoise_jobs 
        ALTER COLUMN status TYPE processingstatus 
        USING status::text::processingstatus;
        
        ALTER TABLE translation_jobs 
        ALTER COLUMN status TYPE processingstatus 
        USING status::text::processingstatus;
        
        ALTER TABLE speaker_jobs 
        ALTER COLUMN status TYPE processingstatus 
        USING status::text::processingstatus;
    """)

    # Revert job type
    op.execute("""
        ALTER TABLE speaker_jobs 
        ALTER COLUMN job_type TYPE jobtype 
        USING job_type::text::jobtype;
    """)

    # Revert other column modifications
    op.alter_column('denoise_jobs', 'error_message',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(),
               existing_nullable=True)
               
    op.alter_column('denoise_jobs', 'stats',
               existing_type=postgresql.JSONB(),
               type_=postgresql.JSON(),
               existing_nullable=True)
               
    op.alter_column('denoise_jobs', 'parameters',
               existing_type=postgresql.JSONB(),
               type_=postgresql.JSON(),
               existing_nullable=True)

    # Drop new enum types
    op.execute("""
        DROP TYPE IF EXISTS processing_status_enum;
        DROP TYPE IF EXISTS job_type_enum;
    """)

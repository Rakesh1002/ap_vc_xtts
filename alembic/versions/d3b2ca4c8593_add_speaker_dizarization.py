"""add speaker dizarization

Revision ID: d3b2ca4c8593
Revises: dba2c3d583e2
Create Date: 2024-11-08 12:28:19.491700

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'd3b2ca4c8593'
down_revision: Union[str, None] = 'dba2c3d583e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create JobType enum if it doesn't exist
    connection = op.get_bind()
    
    # Check if enum exists using raw SQL with text()
    enum_exists = connection.execute(
        text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_type 
                WHERE typname = 'jobtype'
            );
        """)
    ).scalar()
    
    if not enum_exists:
        # Create the enum type
        op.execute(
            text("""
                DO $$ BEGIN
                    CREATE TYPE jobtype AS ENUM (
                        'VOICE_CLONING', 'TRANSLATION', 
                        'SPEAKER_DIARIZATION', 'SPEAKER_EXTRACTION'
                    );
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """)
        )
    else:
        # Alter existing enum if needed
        op.execute(
            text("""
                DO $$ BEGIN
                    ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'SPEAKER_DIARIZATION';
                    ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'SPEAKER_EXTRACTION';
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """)
        )

    # Create speaker_jobs table using existing processingstatus enum
    op.create_table('speaker_jobs',
        sa.Column('job_type', postgresql.ENUM('VOICE_CLONING', 'TRANSLATION', 
                                    'SPEAKER_DIARIZATION', 'SPEAKER_EXTRACTION', 
                                    name='jobtype', 
                                    create_type=False), nullable=False),
        sa.Column('num_speakers', sa.Integer(), nullable=True),
        sa.Column('rttm_path', sa.String(), nullable=True),
        sa.Column('output_paths', sa.JSON(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 
                                  name='processingstatus', 
                                  create_type=False), nullable=True),
        sa.Column('task_id', sa.String(), nullable=True),
        sa.Column('input_path', sa.String(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), 
                 server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_speaker_jobs_id'), 'speaker_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_speaker_jobs_task_id'), 'speaker_jobs', ['task_id'], unique=False)
    
    # Add columns to existing tables - make nullable first
    op.add_column('cloning_jobs', sa.Column('input_path', sa.String(), nullable=True))
    op.add_column('cloning_jobs', sa.Column('parameters', sa.JSON(), nullable=True))
    op.add_column('cloning_jobs', sa.Column('result', sa.JSON(), nullable=True))
    
    # Update existing rows with a default value for input_path
    op.execute(
        text("""
            UPDATE cloning_jobs 
            SET input_path = voices.file_path 
            FROM voices 
            WHERE cloning_jobs.voice_id = voices.id;
        """)
    )
    
    # Now make input_path non-nullable
    op.alter_column('cloning_jobs', 'input_path',
               existing_type=sa.String(),
               nullable=False)
    
    # Update datetime columns
    op.alter_column('cloning_jobs', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True)
    op.alter_column('cloning_jobs', 'updated_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True)
    op.alter_column('cloning_jobs', 'completed_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True)
    
    # Create new index and drop queue column
    op.create_index(op.f('ix_cloning_jobs_task_id'), 'cloning_jobs', ['task_id'], unique=False)
    op.drop_column('cloning_jobs', 'queue')
    
    # Update translation_jobs table
    op.add_column('translation_jobs', sa.Column('parameters', sa.JSON(), nullable=True))
    op.add_column('translation_jobs', sa.Column('result', sa.JSON(), nullable=True))
    op.alter_column('translation_jobs', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True)
    op.alter_column('translation_jobs', 'updated_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True)
    op.alter_column('translation_jobs', 'completed_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True)
    op.create_index(op.f('ix_translation_jobs_task_id'), 'translation_jobs', ['task_id'], unique=False)
    op.drop_column('translation_jobs', 'queue')
    
    # Update voices table
    op.alter_column('voices', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)
    op.create_index(op.f('ix_voices_id'), 'voices', ['id'], unique=False)

def downgrade() -> None:
    # Drop indexes and revert changes
    op.drop_index(op.f('ix_voices_id'), table_name='voices')
    op.alter_column('voices', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)
    
    # Revert translation_jobs changes
    op.add_column('translation_jobs', sa.Column('queue', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.drop_index(op.f('ix_translation_jobs_task_id'), table_name='translation_jobs')
    op.alter_column('translation_jobs', 'completed_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('translation_jobs', 'updated_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('translation_jobs', 'created_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.drop_column('translation_jobs', 'result')
    op.drop_column('translation_jobs', 'parameters')
    
    # Revert cloning_jobs changes
    op.add_column('cloning_jobs', sa.Column('queue', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.drop_index(op.f('ix_cloning_jobs_task_id'), table_name='cloning_jobs')
    op.alter_column('cloning_jobs', 'completed_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('cloning_jobs', 'updated_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('cloning_jobs', 'created_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.drop_column('cloning_jobs', 'result')
    op.drop_column('cloning_jobs', 'parameters')
    op.drop_column('cloning_jobs', 'input_path')
    
    # Drop speaker_jobs table and indexes
    op.drop_index(op.f('ix_speaker_jobs_task_id'), table_name='speaker_jobs')
    op.drop_index(op.f('ix_speaker_jobs_id'), table_name='speaker_jobs')
    op.drop_table('speaker_jobs')
    
    # Don't drop the enum types as they might be used by other tables

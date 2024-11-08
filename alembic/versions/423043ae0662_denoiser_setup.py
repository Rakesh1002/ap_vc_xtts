"""denoiser setup

Revision ID: 423043ae0662
Revises: d3b2ca4c8593
Create Date: 2024-11-08 18:58:01.281018

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '423043ae0662'
down_revision: Union[str, None] = 'd3b2ca4c8593'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Update JobType enum to include DENOISING
    connection = op.get_bind()
    op.execute(
        text("""
            DO $$ BEGIN
                ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'DENOISING';
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
    )

    # Create denoise_jobs table using existing processingstatus enum
    op.create_table('denoise_jobs',
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
        sa.Column('vad_threshold', sa.Float(), nullable=True),
        sa.Column('output_path', sa.String(), nullable=True),
        sa.Column('stats', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index(op.f('ix_denoise_jobs_id'), 'denoise_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_denoise_jobs_task_id'), 'denoise_jobs', ['task_id'], unique=False)

def downgrade() -> None:
    # Drop indexes and table
    op.drop_index(op.f('ix_denoise_jobs_task_id'), table_name='denoise_jobs')
    op.drop_index(op.f('ix_denoise_jobs_id'), table_name='denoise_jobs')
    op.drop_table('denoise_jobs')

    # Note: We don't remove the DENOISING value from jobtype enum
    # as it might be referenced by other tables

"""add spectral denoiser

Revision ID: 3c1b196cd83c
Revises: 1955d9e1c7f7
Create Date: 2024-11-08 21:42:26.220775

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3c1b196cd83c'
down_revision: Union[str, None] = '1955d9e1c7f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create enum type if it doesn't exist
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'denoisermethod') THEN
                CREATE TYPE denoisermethod AS ENUM ('RNNOISE', 'SPECTRAL');
            END IF;
        END
        $$;
    """)
    
    # Add method column with default value
    op.add_column('denoise_jobs',
        sa.Column('method', 
                  postgresql.ENUM('RNNOISE', 'SPECTRAL', name='denoisermethod', create_type=False),
                  server_default='RNNOISE',
                  nullable=False)
    )
    
    # Add parameters column
    op.add_column('denoise_jobs', 
        sa.Column('parameters', sa.JSON(), nullable=True)
    )

def downgrade() -> None:
    # Remove columns
    op.drop_column('denoise_jobs', 'parameters')
    op.drop_column('denoise_jobs', 'method')
    
    # Drop enum type if no other tables are using it
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 
                FROM pg_type 
                WHERE typname = 'denoisermethod'
            ) THEN
                DROP TYPE denoisermethod;
            END IF;
        END
        $$;
    """)

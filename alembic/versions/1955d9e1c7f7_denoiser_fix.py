"""denoiser fix

Revision ID: 1955d9e1c7f7
Revises: 4a9c0096f1cf
Create Date: 2024-11-08 20:33:34.258553

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1955d9e1c7f7'
down_revision: Union[str, None] = '4a9c0096f1cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('denoise_jobs', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))
    op.drop_index('ix_denoise_jobs_task_id', table_name='denoise_jobs')
    op.drop_column('denoise_jobs', 'vad_threshold')
    op.drop_column('denoise_jobs', 'result')
    op.drop_column('denoise_jobs', 'parameters')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('denoise_jobs', sa.Column('parameters', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.add_column('denoise_jobs', sa.Column('result', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.add_column('denoise_jobs', sa.Column('vad_threshold', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
    op.create_index('ix_denoise_jobs_task_id', 'denoise_jobs', ['task_id'], unique=False)
    op.alter_column('denoise_jobs', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True,
               existing_server_default=sa.text('now()'))
    # ### end Alembic commands ###

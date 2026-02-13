"""add_response_format_and_output_schema_to_prompt_templates

Revision ID: c9772e165a8f
Revises: 143f4d69082d
Create Date: 2026-02-13 16:51:59.255907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9772e165a8f'
down_revision: Union[str, Sequence[str], None] = '143f4d69082d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('prompt_templates', sa.Column('response_format', sa.String(length=50), nullable=True))
    op.add_column('prompt_templates', sa.Column('output_schema', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('prompt_templates', 'output_schema')
    op.drop_column('prompt_templates', 'response_format')

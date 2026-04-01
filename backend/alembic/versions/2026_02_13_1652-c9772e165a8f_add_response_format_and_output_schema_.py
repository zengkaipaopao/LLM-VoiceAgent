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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("prompt_templates")}

    if "response_format" not in columns:
        op.add_column("prompt_templates", sa.Column("response_format", sa.String(length=50), nullable=True))
    if "output_schema" not in columns:
        op.add_column(
            "prompt_templates",
            sa.Column("output_schema", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("prompt_templates")}

    if "output_schema" in columns:
        op.drop_column("prompt_templates", "output_schema")
    if "response_format" in columns:
        op.drop_column("prompt_templates", "response_format")

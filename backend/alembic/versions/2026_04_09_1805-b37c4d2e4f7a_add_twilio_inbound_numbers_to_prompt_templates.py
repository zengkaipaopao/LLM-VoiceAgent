"""add twilio inbound numbers to prompt templates

Revision ID: b37c4d2e4f7a
Revises: 9f3c1c8f2b1a
Create Date: 2026-04-09 18:05:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b37c4d2e4f7a"
down_revision: Union[str, Sequence[str], None] = "9f3c1c8f2b1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {column["name"] for column in inspector.get_columns("prompt_templates")}
    if "twilio_inbound_numbers" not in columns:
        op.add_column(
            "prompt_templates",
            sa.Column(
                "twilio_inbound_numbers",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {column["name"] for column in inspector.get_columns("prompt_templates")}
    if "twilio_inbound_numbers" in columns:
        op.drop_column("prompt_templates", "twilio_inbound_numbers")

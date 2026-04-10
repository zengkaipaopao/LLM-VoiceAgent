"""add twilio incoming default prompt flag

Revision ID: 9f3c1c8f2b1a
Revises: 366cf503647a
Create Date: 2026-04-09 17:20:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f3c1c8f2b1a"
down_revision: Union[str, Sequence[str], None] = "366cf503647a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {column["name"] for column in inspector.get_columns("prompt_templates")}
    if "is_twilio_incoming_default" not in columns:
        op.add_column(
            "prompt_templates",
            sa.Column(
                "is_twilio_incoming_default",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    indexes = {index["name"] for index in inspector.get_indexes("prompt_templates")}
    if "ix_prompt_templates_is_twilio_incoming_default" not in indexes:
        op.create_index(
            "ix_prompt_templates_is_twilio_incoming_default",
            "prompt_templates",
            ["is_twilio_incoming_default"],
            unique=False,
        )

    # Allow at most one prompt to be flagged as the direct inbound Twilio default.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_prompt_templates_twilio_incoming_default_true
        ON prompt_templates (is_twilio_incoming_default)
        WHERE is_twilio_incoming_default IS TRUE
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    op.execute("DROP INDEX IF EXISTS uq_prompt_templates_twilio_incoming_default_true")

    indexes = {index["name"] for index in inspector.get_indexes("prompt_templates")}
    if "ix_prompt_templates_is_twilio_incoming_default" in indexes:
        op.drop_index("ix_prompt_templates_is_twilio_incoming_default", table_name="prompt_templates")

    columns = {column["name"] for column in inspector.get_columns("prompt_templates")}
    if "is_twilio_incoming_default" in columns:
        op.drop_column("prompt_templates", "is_twilio_incoming_default")

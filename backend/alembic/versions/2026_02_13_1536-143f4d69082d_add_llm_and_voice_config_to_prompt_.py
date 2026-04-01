"""add_llm_and_voice_config_to_prompt_template

Revision ID: 143f4d69082d
Revises:
Create Date: 2026-02-13 15:34:30.575446
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "143f4d69082d"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_exists(indexes: list[dict], index_name: str) -> bool:
    return any(index.get("name") == index_name for index in indexes)


def upgrade() -> None:
    """Create baseline schema for a clean database."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    if not inspector.has_table("prompt_templates"):
        op.create_table(
            "prompt_templates",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("code", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=50), nullable=True),
            sa.Column("system_prompt", sa.Text(), nullable=False),
            sa.Column("extraction_prompt", sa.Text(), nullable=True),
            sa.Column("variables", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("example_conversations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("extraction_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("llm_provider", sa.String(length=50), nullable=True),
            sa.Column("llm_model", sa.String(length=100), nullable=True),
            sa.Column("temperature", sa.Float(), nullable=True),
            sa.Column("max_tokens", sa.Integer(), nullable=True),
            sa.Column("voice_provider", sa.String(length=50), nullable=True),
            sa.Column("voice_id", sa.String(length=100), nullable=True),
            sa.Column("voice_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("version", sa.Integer(), nullable=True, server_default=sa.text("1")),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("code", name="uq_prompt_templates_code"),
        )

    inspector.clear_cache()
    prompt_indexes = inspector.get_indexes("prompt_templates") if inspector.has_table("prompt_templates") else []
    if not _index_exists(prompt_indexes, "ix_prompt_templates_code"):
        op.create_index("ix_prompt_templates_code", "prompt_templates", ["code"], unique=True)
    if not _index_exists(prompt_indexes, "ix_prompt_templates_category"):
        op.create_index("ix_prompt_templates_category", "prompt_templates", ["category"], unique=False)
    if not _index_exists(prompt_indexes, "ix_prompt_templates_is_active"):
        op.create_index("ix_prompt_templates_is_active", "prompt_templates", ["is_active"], unique=False)

    if not inspector.has_table("calls"):
        op.create_table(
            "calls",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
            sa.Column("direction", sa.String(length=20), nullable=False),
            sa.Column("counterpart", sa.String(length=50), nullable=False),
            sa.Column("caller_name", sa.String(length=100), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("answered_at", sa.DateTime(), nullable=True),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'ringing'")),
            sa.Column("handler_type", sa.String(length=20), nullable=True, server_default=sa.text("'ai'")),
            sa.Column("is_answered", sa.Boolean(), nullable=True, server_default=sa.text("false")),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("transcript", sa.Text(), nullable=True),
            sa.Column("ai_confidence", sa.Integer(), nullable=True),
            sa.Column("transferred_at", sa.DateTime(), nullable=True),
            sa.Column("transfer_reason", sa.String(length=200), nullable=True),
            sa.Column("sip_call_id", sa.String(length=100), nullable=True),
            sa.Column("sip_from", sa.String(length=100), nullable=True),
            sa.Column("sip_to", sa.String(length=100), nullable=True),
            sa.Column("prompt_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["prompt_id"], ["prompt_templates.id"], name="fk_calls_prompt", ondelete="SET NULL"),
        )

    inspector.clear_cache()
    calls_indexes = inspector.get_indexes("calls") if inspector.has_table("calls") else []
    if not _index_exists(calls_indexes, "ix_calls_counterpart"):
        op.create_index("ix_calls_counterpart", "calls", ["counterpart"], unique=False)
    if not _index_exists(calls_indexes, "ix_calls_started_at"):
        op.create_index("ix_calls_started_at", "calls", ["started_at"], unique=False)
    if not _index_exists(calls_indexes, "ix_calls_status"):
        op.create_index("ix_calls_status", "calls", ["status"], unique=False)
    if not _index_exists(calls_indexes, "ix_calls_handler_type"):
        op.create_index("ix_calls_handler_type", "calls", ["handler_type"], unique=False)
    if not _index_exists(calls_indexes, "ix_calls_prompt_id"):
        op.create_index("ix_calls_prompt_id", "calls", ["prompt_id"], unique=False)
    if not _index_exists(calls_indexes, "ix_calls_sip_call_id"):
        op.create_index("ix_calls_sip_call_id", "calls", ["sip_call_id"], unique=False)

    if not inspector.has_table("appointments"):
        op.create_table(
            "appointments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
            sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("caller_name", sa.String(length=100), nullable=False),
            sa.Column("company", sa.String(length=200), nullable=True),
            sa.Column("appointment", sa.DateTime(), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=True),
            sa.Column("amount", sa.String(length=100), nullable=True),
            sa.Column("address", sa.Text(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("extra_request", sa.Text(), nullable=True),
            sa.Column("raw_messages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("operation", sa.String(length=10), nullable=True),
            sa.Column("is_handled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        )

    inspector.clear_cache()
    appointments_indexes = inspector.get_indexes("appointments") if inspector.has_table("appointments") else []
    if not _index_exists(appointments_indexes, "ix_appointments_call_id"):
        op.create_index("ix_appointments_call_id", "appointments", ["call_id"], unique=False)
    if not _index_exists(appointments_indexes, "ix_appointments_timestamp"):
        op.create_index("ix_appointments_timestamp", "appointments", ["timestamp"], unique=False)
    if not _index_exists(appointments_indexes, "ix_appointments_caller_name"):
        op.create_index("ix_appointments_caller_name", "appointments", ["caller_name"], unique=False)


def downgrade() -> None:
    """Drop baseline schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("appointments"):
        op.drop_table("appointments")
    if inspector.has_table("calls"):
        op.drop_table("calls")
    if inspector.has_table("prompt_templates"):
        op.drop_table("prompt_templates")

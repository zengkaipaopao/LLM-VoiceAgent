"""add dynamic schema fields to appointment

Revision ID: 366cf503647a
Revises: c9772e165a8f
Create Date: 2026-03-04 12:15:43.599970

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '366cf503647a'
down_revision: Union[str, Sequence[str], None] = 'c9772e165a8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {column["name"] for column in inspector.get_columns("appointments")}
    if "prompt_id" not in columns:
        op.add_column("appointments", sa.Column("prompt_id", sa.UUID(), nullable=True))
    if "type_name" not in columns:
        op.add_column("appointments", sa.Column("type_name", sa.String(length=50), nullable=True))
    if "extracted_data" not in columns:
        op.add_column(
            "appointments",
            sa.Column("extracted_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )

    indexes = {index["name"] for index in inspector.get_indexes("appointments")}
    if op.f("ix_appointments_prompt_id") not in indexes:
        op.create_index(op.f("ix_appointments_prompt_id"), "appointments", ["prompt_id"], unique=False)
    if op.f("ix_appointments_type_name") not in indexes:
        op.create_index(op.f("ix_appointments_type_name"), "appointments", ["type_name"], unique=False)

    foreign_keys = inspector.get_foreign_keys("appointments")
    has_prompt_fk = any(
        fk.get("referred_table") == "prompt_templates" and fk.get("constrained_columns") == ["prompt_id"]
        for fk in foreign_keys
    )
    if not has_prompt_fk:
        op.create_foreign_key(
            "fk_appointments_prompt_templates",
            "appointments",
            "prompt_templates",
            ["prompt_id"],
            ["id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    foreign_keys = inspector.get_foreign_keys("appointments")
    for fk in foreign_keys:
        if fk.get("referred_table") == "prompt_templates" and fk.get("constrained_columns") == ["prompt_id"]:
            if fk.get("name"):
                op.drop_constraint(fk["name"], "appointments", type_="foreignkey")
            break

    indexes = {index["name"] for index in inspector.get_indexes("appointments")}
    if op.f("ix_appointments_type_name") in indexes:
        op.drop_index(op.f("ix_appointments_type_name"), table_name="appointments")
    if op.f("ix_appointments_prompt_id") in indexes:
        op.drop_index(op.f("ix_appointments_prompt_id"), table_name="appointments")

    columns = {column["name"] for column in inspector.get_columns("appointments")}
    if "extracted_data" in columns:
        op.drop_column("appointments", "extracted_data")
    if "type_name" in columns:
        op.drop_column("appointments", "type_name")
    if "prompt_id" in columns:
        op.drop_column("appointments", "prompt_id")

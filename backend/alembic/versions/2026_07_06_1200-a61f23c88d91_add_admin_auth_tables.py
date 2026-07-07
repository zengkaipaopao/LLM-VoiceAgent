"""add administrative users and sessions

Revision ID: a61f23c88d91
Revises: b37c4d2e4f7a
Create Date: 2026-07-06 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a61f23c88d91"
down_revision: Union[str, Sequence[str], None] = "b37c4d2e4f7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=True),
        sa.Column("auth_provider", sa.String(length=32), nullable=False),
        sa.Column("external_subject", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"])

    op.create_table(
        "admin_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("admin_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_admin_sessions_user_id", "admin_sessions", ["user_id"])
    op.create_index("ix_admin_sessions_token_hash", "admin_sessions", ["token_hash"])
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_table("admin_sessions")
    op.drop_table("admin_users")

"""normalize legacy call enum columns to varchar

Revision ID: 5c8142e97a31
Revises: ef72a501c144
Create Date: 2026-07-06 21:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "5c8142e97a31"
down_revision: Union[str, Sequence[str], None] = "ef72a501c144"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_type(table: str, column: str) -> str:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table
              AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    )
    return str(result.scalar_one_or_none() or "")


def upgrade() -> None:
    # PostgreSQL enum-backed defaults keep a dependency on the enum type even
    # after the column itself is converted, so remove them before conversion.
    op.execute(sa.text("ALTER TABLE calls ALTER COLUMN status DROP DEFAULT"))
    op.execute(sa.text("ALTER TABLE calls ALTER COLUMN handler_type DROP DEFAULT"))

    for column, length in (
        ("direction", 20),
        ("status", 20),
        ("handler_type", 20),
    ):
        if _column_type("calls", column) == "USER-DEFINED":
            op.execute(
                sa.text(
                    f'ALTER TABLE calls ALTER COLUMN "{column}" '
                    f'TYPE VARCHAR({length}) USING "{column}"::text'
                )
            )

    op.execute(sa.text("ALTER TABLE calls ALTER COLUMN status SET DEFAULT 'ringing'"))
    op.execute(sa.text("ALTER TABLE calls ALTER COLUMN handler_type SET DEFAULT 'ai'"))

    # The enum types are no longer referenced after all three columns are normalized.
    op.execute(sa.text("DROP TYPE IF EXISTS call_direction"))
    op.execute(sa.text("DROP TYPE IF EXISTS call_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS handler_type"))


def downgrade() -> None:
    # String columns are intentionally retained: values may have expanded since upgrade.
    pass

"""convert user ids to uuid

Revision ID: 202607110002
Revises: 202607080001
Create Date: 2026-07-11 23:59:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607110002"
down_revision: str | None = "202607080001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "id",
        existing_type=sa.String(length=36),
        type_=postgresql.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="id::uuid",
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "id",
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.String(length=36),
        existing_nullable=False,
        postgresql_using="id::text",
    )
"""add claims.verification_failed

Revision ID: c4e8a1d27b90
Revises: b3d9e4f1c2a7
Create Date: 2026-11-07 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e8a1d27b90"
down_revision: str | None = "b3d9e4f1c2a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "claims",
        sa.Column("verification_failed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("claims", "verification_failed")

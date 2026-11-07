"""add indexes for the submissions and score event queries

Revision ID: d5f2b7c3e8a1
Revises: c4e8a1d27b90
Create Date: 2026-11-07 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5f2b7c3e8a1"
down_revision: str | None = "c4e8a1d27b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_submissions_user_created", "submissions", ["user_id", sa.text("created_at DESC")]
    )
    op.create_index("ix_submissions_user_status", "submissions", ["user_id", "status"])
    op.create_index(
        "ix_source_score_events_source_created",
        "source_score_events",
        ["source_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_source_score_events_source_created", table_name="source_score_events")
    op.drop_index("ix_submissions_user_status", table_name="submissions")
    op.drop_index("ix_submissions_user_created", table_name="submissions")

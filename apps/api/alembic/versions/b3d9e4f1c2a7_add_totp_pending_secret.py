"""add users.totp_pending_secret_encrypted

Revision ID: b3d9e4f1c2a7
Revises: 80038e602672
Create Date: 2026-10-07 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3d9e4f1c2a7"
down_revision: str | None = "80038e602672"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_pending_secret_encrypted", sa.String(), nullable=True))
    # Users who started enrollment but never confirmed it had their secret in
    # the active column with mfa_enabled = false. Move it to the pending slot
    # so they can finish confirming with the QR code they already scanned.
    op.execute(
        "UPDATE users SET totp_pending_secret_encrypted = totp_secret_encrypted, "
        "totp_secret_encrypted = NULL "
        "WHERE mfa_enabled = false AND totp_secret_encrypted IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET totp_secret_encrypted = totp_pending_secret_encrypted "
        "WHERE mfa_enabled = false AND totp_pending_secret_encrypted IS NOT NULL"
    )
    op.drop_column("users", "totp_pending_secret_encrypted")

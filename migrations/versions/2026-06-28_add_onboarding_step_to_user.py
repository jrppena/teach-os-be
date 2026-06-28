"""add onboarding_step to user

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-06-28

Adds the ``onboarding_step`` column to the ``user`` table to track a teacher's
progress through the guided onboarding wizard (resumable; stores the step name,
not a boolean). New rows default to ``WELCOME``. Existing rows pre-date
onboarding, so they are backfilled to ``COMPLETED`` to avoid forcing current
teachers through the wizard.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "onboarding_step",
            sa.String(20),
            nullable=False,
            server_default="WELCOME",
        ),
    )
    # Existing users pre-date onboarding — mark them complete so they are not
    # redirected into the wizard. New inserts keep the WELCOME server default.
    op.execute("UPDATE \"user\" SET onboarding_step = 'COMPLETED'")


def downgrade() -> None:
    op.drop_column("user", "onboarding_step")

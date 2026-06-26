"""add placeholder_count to lesson_plan

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-26

Adds ``placeholder_count`` (INT NOT NULL DEFAULT 0) to the existing ``lesson_plan``
table. The column tracks how many ``[Teacher to complete]`` placeholders the generated
plan contains. Existing rows default to 0.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lesson_plan",
        sa.Column("placeholder_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("lesson_plan", "placeholder_count", server_default=None)


def downgrade() -> None:
    op.drop_column("lesson_plan", "placeholder_count")

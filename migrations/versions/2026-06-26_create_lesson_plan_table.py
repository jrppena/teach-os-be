"""create lesson plan table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-26

Creates ``lesson_plan`` (one row per generated ILAW plan, owned by a user). The
full generated plan is stored as JSONB in ``plan_json``; header fields are
denormalized into columns so the dashboard list can be served without parsing the
JSON. Cascade-deletes when the parent ``user`` row is removed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lesson_plan",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("learning_areas", sa.String(length=255), nullable=False),
        sa.Column("grade_level_and_section", sa.String(length=255), nullable=False),
        sa.Column("sessions_label", sa.String(length=100), nullable=False),
        sa.Column("sessions", sa.Integer(), nullable=False),
        sa.Column("placeholder_count", sa.Integer(), nullable=False),
        sa.Column("provider_used", sa.String(length=20), nullable=False),
        sa.Column("plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("lesson_plan_user_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("lesson_plan_pkey")),
    )
    op.create_index(
        op.f("lesson_plan_user_id_idx"),
        "lesson_plan",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("lesson_plan_user_id_idx"), table_name="lesson_plan")
    op.drop_table("lesson_plan")

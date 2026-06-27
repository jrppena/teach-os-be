"""create curriculum tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-27

Creates the two global reference tables for DepEd curriculum data:
``grade_level`` (Grade 1-12) and ``learning_area`` (subjects per grade, with an
optional Strengthened-SHS ``track``). ``learning_area`` cascade-deletes with its
parent grade level. Column/constraint names follow the Postgres naming convention
configured in ``src/database.py``. Data is loaded by the follow-up seed migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "grade_level",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("curriculum", sa.String(length=50), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("grade_level_pkey")),
    )
    op.create_index(
        op.f("grade_level_code_idx"),
        "grade_level",
        ["code"],
        unique=True,
    )

    op.create_table(
        "learning_area",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("grade_level_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column(
            "category",
            sa.String(length=20),
            server_default="CORE",
            nullable=False,
        ),
        sa.Column("track", sa.String(length=20), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["grade_level_id"],
            ["grade_level.id"],
            name=op.f("learning_area_grade_level_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("learning_area_pkey")),
        sa.UniqueConstraint(
            "grade_level_id",
            "name",
            name="learning_area_grade_level_id_name_key",
        ),
    )
    op.create_index(
        op.f("learning_area_grade_level_id_idx"),
        "learning_area",
        ["grade_level_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("learning_area_grade_level_id_idx"), table_name="learning_area")
    op.drop_table("learning_area")
    op.drop_index(op.f("grade_level_code_idx"), table_name="grade_level")
    op.drop_table("grade_level")

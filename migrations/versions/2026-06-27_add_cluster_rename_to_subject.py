"""add cluster table and rename learning_area to subject

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-27

Structural changes for the Strengthened SHS curriculum refactor:

1. Creates ``cluster`` — one row per SHS elective cluster (e.g. STEM, Hospitality).
2. Creates ``cluster_grade_level`` — M2M: which grade levels offer a cluster.
3. Renames ``learning_area`` → ``subject`` and all its constraints/indexes.
4. Adds ``subject.cluster_id`` FK (``ondelete SET NULL``) for elective subjects.
5. Drops ``subject.track`` (track now lives on ``cluster``).
6. Alters ``subject.grade_level_id`` to nullable (NULL for electives).
7. Replaces the single unique constraint with two partial ones (core vs. elective).
8. Adds the XOR CHECK ensuring exactly one of grade_level_id / cluster_id is set.

Data is loaded by the follow-up seed migration (a7b8c9d0e1f2 → b8c9d0e1f2a3).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. Create cluster table ─────────────────────────────────────────────
    op.create_table(
        "cluster",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("track", sa.String(length=20), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("cluster_pkey")),
        sa.UniqueConstraint("name", name="cluster_name_key"),
    )

    # ── 2. Create cluster_grade_level M2M table ─────────────────────────────
    op.create_table(
        "cluster_grade_level",
        sa.Column("cluster_id", sa.Uuid(), nullable=False),
        sa.Column("grade_level_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["cluster.id"],
            name=op.f("cluster_grade_level_cluster_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["grade_level_id"],
            ["grade_level.id"],
            name=op.f("cluster_grade_level_grade_level_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "cluster_id", "grade_level_id", name=op.f("cluster_grade_level_pkey")
        ),
    )

    # ── 3. Rename learning_area → subject ───────────────────────────────────
    op.rename_table("learning_area", "subject")

    # Rename PK constraint
    op.execute(
        "ALTER TABLE subject RENAME CONSTRAINT learning_area_pkey TO subject_pkey"
    )
    # Rename FK constraint
    op.execute(
        "ALTER TABLE subject RENAME CONSTRAINT "
        "learning_area_grade_level_id_fkey TO subject_grade_level_id_fkey"
    )
    # Rename index on grade_level_id
    op.execute(
        "ALTER INDEX learning_area_grade_level_id_idx "
        "RENAME TO subject_grade_level_id_idx"
    )
    # Drop the old unique constraint (will be replaced by two below)
    op.drop_constraint(
        "learning_area_grade_level_id_name_key",
        "subject",
        type_="unique",
    )

    # ── 4. Add cluster_id FK column ─────────────────────────────────────────
    op.add_column(
        "subject",
        sa.Column("cluster_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f("subject_cluster_id_fkey"),
        "subject",
        "cluster",
        ["cluster_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("subject_cluster_id_idx"), "subject", ["cluster_id"], unique=False)

    # ── 5. Drop track column ────────────────────────────────────────────────
    op.drop_column("subject", "track")

    # ── 6. Make grade_level_id nullable ────────────────────────────────────
    op.alter_column("subject", "grade_level_id", nullable=True)

    # ── 7. Add two new unique constraints ──────────────────────────────────
    op.create_unique_constraint(
        "subject_grade_level_id_name_key",
        "subject",
        ["grade_level_id", "name"],
    )
    op.create_unique_constraint(
        "subject_cluster_id_name_key",
        "subject",
        ["cluster_id", "name"],
    )

    # ── 8. Add XOR CHECK constraint ─────────────────────────────────────────
    op.create_check_constraint(
        "subject_xor_grade_level_or_cluster_check",
        "subject",
        "(grade_level_id IS NULL) != (cluster_id IS NULL)",
    )


def downgrade() -> None:
    # Reverse in opposite order.

    # ── 8. Drop XOR CHECK ───────────────────────────────────────────────────
    op.drop_constraint(
        "subject_xor_grade_level_or_cluster_check",
        "subject",
        type_="check",
    )

    # ── 7. Drop new unique constraints ──────────────────────────────────────
    op.drop_constraint("subject_cluster_id_name_key", "subject", type_="unique")
    op.drop_constraint("subject_grade_level_id_name_key", "subject", type_="unique")

    # ── 6. Restore grade_level_id NOT NULL ─────────────────────────────────
    op.alter_column("subject", "grade_level_id", nullable=False)

    # ── 5. Restore track column ─────────────────────────────────────────────
    op.add_column(
        "subject",
        sa.Column("track", sa.String(length=20), nullable=True),
    )

    # ── 4. Drop cluster_id FK and column ────────────────────────────────────
    op.drop_index(op.f("subject_cluster_id_idx"), table_name="subject")
    op.drop_constraint(op.f("subject_cluster_id_fkey"), "subject", type_="foreignkey")
    op.drop_column("subject", "cluster_id")

    # ── 3. Rename subject → learning_area ──────────────────────────────────
    op.create_unique_constraint(
        "learning_area_grade_level_id_name_key",
        "subject",
        ["grade_level_id", "name"],
    )
    op.execute(
        "ALTER INDEX subject_grade_level_id_idx "
        "RENAME TO learning_area_grade_level_id_idx"
    )
    op.execute(
        "ALTER TABLE subject RENAME CONSTRAINT "
        "subject_grade_level_id_fkey TO learning_area_grade_level_id_fkey"
    )
    op.execute(
        "ALTER TABLE subject RENAME CONSTRAINT subject_pkey TO learning_area_pkey"
    )
    op.rename_table("subject", "learning_area")

    # ── 2 & 1. Drop cluster tables ───────────────────────────────────────────
    op.drop_table("cluster_grade_level")
    op.drop_table("cluster")

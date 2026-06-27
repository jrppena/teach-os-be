"""add school fields to user

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-27

Adds DepEd school header fields (school_name, region, division, district,
school_address) to the ``user`` table. These are used to populate the school
header block in exported DOCX lesson plans. All columns default to empty string
so existing rows require no backfill.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user", sa.Column("school_name", sa.String(255), nullable=False, server_default=""))
    op.add_column("user", sa.Column("region", sa.String(100), nullable=False, server_default=""))
    op.add_column("user", sa.Column("division", sa.String(100), nullable=False, server_default=""))
    op.add_column("user", sa.Column("district", sa.String(100), nullable=False, server_default=""))
    op.add_column("user", sa.Column("school_address", sa.String(500), nullable=False, server_default=""))
    # Remove server defaults after backfill so new inserts use the app-level default
    op.alter_column("user", "school_name", server_default=None)
    op.alter_column("user", "region", server_default=None)
    op.alter_column("user", "division", server_default=None)
    op.alter_column("user", "district", server_default=None)
    op.alter_column("user", "school_address", server_default=None)


def downgrade() -> None:
    op.drop_column("user", "school_address")
    op.drop_column("user", "district")
    op.drop_column("user", "division")
    op.drop_column("user", "region")
    op.drop_column("user", "school_name")

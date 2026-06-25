"""create user table

Revision ID: f1a2b3c4d5e6
Revises:
Create Date: 2026-06-25

Initial schema: the ``user`` table backing Firebase auth. Column/constraint names
follow the Postgres naming convention configured in ``src/database.py``.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column(
            "role",
            sa.String(length=20),
            server_default="USER",
            nullable=False,
        ),
        sa.Column("bio", sa.String(), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("user_pkey")),
    )
    op.create_index(
        op.f("user_firebase_uid_idx"),
        "user",
        ["firebase_uid"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("user_firebase_uid_idx"), table_name="user")
    op.drop_table("user")

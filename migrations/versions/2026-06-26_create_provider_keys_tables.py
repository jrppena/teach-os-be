"""create provider keys tables

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-06-26

Creates ``provider_setting`` (one row per user — active-provider preference) and
``provider_key`` (one row per user+provider — Fernet-encrypted API key). Both
cascade-delete when the parent ``user`` row is removed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_setting",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "active_provider",
            sa.String(length=20),
            server_default="gemini",
            nullable=False,
        ),
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
            name=op.f("provider_setting_user_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("provider_setting_pkey")),
    )

    op.create_table(
        "provider_key",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
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
            name=op.f("provider_key_user_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("provider_key_pkey")),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            name="provider_key_user_id_provider_key",
        ),
    )
    op.create_index(
        op.f("provider_key_user_id_idx"),
        "provider_key",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("provider_key_user_id_idx"), table_name="provider_key")
    op.drop_table("provider_key")
    op.drop_table("provider_setting")

"""Settings domain ORM models.

Two tables on the shared ``Base``:

- ``provider_setting`` — one row per user; the active-provider preference.
- ``provider_key`` — one row per (user, provider); the encrypted API key.

Both cascade-delete when the parent ``user`` row is removed.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class ProviderSetting(Base):
    """Per-user active-provider preference.

    One row per user.  Separated from ``ProviderKey`` so the teacher can select
    an active provider before entering a key (the amber "add a key" hint).

    Inputs: populated/upserted by ``settings_service.update_provider_keys``.
    Outputs: read by ``settings_service.get_provider_keys``.
    Side effects: persisted to the ``provider_setting`` table.
    """

    __tablename__ = "provider_setting"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    active_provider: Mapped[str] = mapped_column(
        String(20), default="gemini", server_default="gemini"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProviderKey(Base):
    """Per-user, per-provider encrypted API key.

    One row per (user_id, provider) pair — enforced by a UNIQUE constraint.
    The ``encrypted_key`` column stores a Fernet ciphertext; the plaintext is
    never written to or read from the DB directly.

    Inputs: populated/upserted by ``settings_service.update_provider_keys``.
    Outputs: read and decrypted by ``settings_service.get_provider_keys``.
    Side effects: persisted to the ``provider_key`` table.
    """

    __tablename__ = "provider_key"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="provider_key_user_id_provider_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(20))
    encrypted_key: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

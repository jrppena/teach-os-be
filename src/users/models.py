"""Users domain ORM model.

Defines the ``user`` table — the canonical profile linked to a Firebase account
via ``firebase_uid``. SQLAlchemy 2.0 typed mappings on the shared ``Base`` so the
Postgres naming convention in ``src/database.py`` applies.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class User(Base):
    """A registered teacher's canonical profile row.

    One row per Firebase account. ``firebase_uid`` is the foreign identity from
    Firebase Auth and the lookup key used by the auth flow. ``role`` defaults to
    ``USER``; ``created_at`` is set server-side; ``last_login`` is touched on each
    authenticated profile fetch.

    Inputs: populated by ``user_service.create_user`` from a ``RegisterInput``.
    Outputs: hydrated into ``UserResponse`` for API responses.
    Side effects: persisted to the ``user`` table.
    """

    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="USER", server_default="USER")
    bio: Mapped[str] = mapped_column(String, default="", server_default="")
    school_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    region: Mapped[str] = mapped_column(String(100), default="", server_default="")
    division: Mapped[str] = mapped_column(String(100), default="", server_default="")
    district: Mapped[str] = mapped_column(String(100), default="", server_default="")
    school_address: Mapped[str] = mapped_column(String(500), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

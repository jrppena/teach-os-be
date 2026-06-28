"""Feedback domain ORM model.

Defines the ``feedback`` table — one row per submission, linked to the author's
``user`` row via ``user_id``. SQLAlchemy 2.0 typed mappings on the shared
``Base`` so the Postgres naming convention in ``src/database.py`` applies. The
row cascade-deletes when the parent ``user`` is removed.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Feedback(Base):
    """A single piece of product feedback submitted by a teacher.

    One row per submission. ``category`` stores a ``FeedbackCategory`` value;
    ``rating`` is an optional 1–5 score; ``message`` is the free-form body.
    ``created_at`` is set server-side.

    Inputs: populated by ``feedback_service.create_feedback`` from a
    ``FeedbackCreate`` payload.
    Outputs: hydrated into ``FeedbackResponse`` for API responses.
    Side effects: persisted to the ``feedback`` table.
    """

    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        index=True,
    )
    category: Mapped[str] = mapped_column(String(40), default="GENERAL", server_default="GENERAL")
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

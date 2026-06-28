"""Feedback domain service.

Async data-access helper for the ``feedback`` table, consumed by the feedback
endpoint in ``src/feedback/router.py``. SQLAlchemy 2.0 async only — no
blocking/sync sessions.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.feedback.models import Feedback
from src.feedback.schemas import FeedbackCreate


async def create_feedback(
    db: AsyncSession, user_id: uuid.UUID, payload: FeedbackCreate
) -> Feedback:
    """Insert a new feedback row authored by the given user.

    Inputs: an async session, the author's internal user UUID, and a validated
    ``FeedbackCreate`` payload.
    Outputs: the persisted, refreshed ``Feedback`` row.
    Side effects: inserts one row and commits.
    """
    feedback = Feedback(
        user_id=user_id,
        category=payload.category.value,
        rating=payload.rating,
        message=payload.message,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return feedback

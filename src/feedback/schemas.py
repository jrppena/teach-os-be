"""Feedback domain schemas.

Request/response models for the feedback endpoint. Like ``src/users/schemas.py``,
these use a camelCase alias generator so JSON matches the FE's camelCase shapes
while populating from snake_case ORM attributes.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from pydantic.alias_generators import to_camel

from src.feedback.constants import FeedbackCategory


class _CamelModel(BaseModel):
    """Base config: emit/accept camelCase, also accept field names, read from ORM."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class FeedbackCreate(_CamelModel):
    """Body for ``POST /feedback``.

    Sent by the FE feedback form. ``category`` defaults to ``GENERAL``; ``rating``
    is an optional 1–5 score; ``message`` is required (1–2000 chars).

    Inputs: camelCase JSON body.
    Outputs: validated object consumed by ``feedback_service.create_feedback``.
    Side effects: none.
    """

    category: FeedbackCategory = FeedbackCategory.GENERAL
    rating: int | None = Field(default=None, ge=1, le=5)
    message: str = Field(min_length=1, max_length=2000)


class FeedbackResponse(_CamelModel):
    """Response model for the feedback endpoint — the FE ``Feedback`` shape.

    Inputs: validated from a ``Feedback`` ORM instance (``from_attributes``).
    Outputs: camelCase JSON with ``id`` as a string and ``createdAt`` as ISO-8601.
    Side effects: none.
    """

    id: uuid.UUID
    category: FeedbackCategory
    rating: int | None
    message: str
    created_at: datetime

    @field_serializer("id", when_used="json")
    def _serialize_id(self, value: uuid.UUID) -> str:
        # ``id`` is a UUID on the ORM model; emit it as a plain string for the FE.
        return str(value)

    @field_serializer("created_at", when_used="json")
    def _serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()

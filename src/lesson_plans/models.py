"""Lesson-plans domain ORM model.

One table on the shared ``Base``:

- ``lesson_plan`` — one row per generated plan, owned by a user. The full
  generated ILAW plan is stored as JSONB in ``plan_json``; a few header fields are
  denormalized into columns so the dashboard list can be served without parsing
  every JSON blob. Cascade-deletes when the parent ``user`` row is removed.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class LessonPlan(Base):
    """A persisted, AI-generated ILAW lesson plan.

    Inputs: created by ``lesson_plans.service.generate_and_save`` after the
    provider returns a validated plan.
    Outputs: read by the list/detail service helpers.
    Side effects: persisted to the ``lesson_plan`` table. The denormalized
    ``title``/``learning_areas``/``grade_level_and_section``/``sessions_label``
    columns mirror the corresponding ``lessonInformation`` fields so list rows map
    1:1 to ``LessonPlanSummary``; ``plan_json`` holds the full ``GeneratedLessonPlan``
    (camelCase, as returned to the FE).
    """

    __tablename__ = "lesson_plan"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    learning_areas: Mapped[str] = mapped_column(String(255))
    grade_level_and_section: Mapped[str] = mapped_column(String(255))
    sessions_label: Mapped[str] = mapped_column(String(100))
    sessions: Mapped[int] = mapped_column(Integer)
    placeholder_count: Mapped[int] = mapped_column(Integer)
    provider_used: Mapped[str] = mapped_column(String(20))
    plan_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

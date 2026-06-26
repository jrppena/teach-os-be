"""Lesson-plans domain schemas.

Pydantic v2 request/response models for the lesson-plan generation endpoints.
Uses the same camelCase alias generator pattern as ``src/settings/schemas.py`` so
the FE exchanges camelCase JSON while the DB/service layer stays snake_case.

The ``GeneratedLessonPlan`` family is an exact mirror of the FE's
``GeneratedLessonPlan`` type (teacher-os-fe/src/features/generate/types.ts). It is
used both to **validate** the JSON returned by the AI provider and as the shape
that is stored and returned to the client.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from src.settings.schemas import ProviderId


class _CamelModel(BaseModel):
    """Base config: emit/accept camelCase, also accept field names, read from ORM."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# ── Generation request (mirrors the FE wizard inputs) ────────────────────────────
class LessonPlanGenerateRequest(_CamelModel):
    """Body for ``POST /lesson-plans`` — the Step 1 + Step 2 wizard inputs.

    Inputs: camelCase JSON from the FE generate wizard.
    Outputs: consumed by ``lesson_plans.service.generate_and_save``.
    Side effects: none at schema level. ``sessions`` is bounded 1..5 to match the
    FE stepper; ``competencies`` must contain at least one entry.
    """

    lesson_title: str = Field(min_length=1)
    grade_level: str = Field(min_length=1)
    learning_area: str = Field(min_length=1)
    term: str = ""
    week: str = ""
    teacher_name: str = ""
    section: str = ""
    sessions: int = Field(default=1, ge=1, le=5)
    minutes_per_session: int = Field(default=45, ge=1)
    references: list[str] = Field(default_factory=list)
    ai_declaration: str = ""
    competencies: list[str] = Field(min_length=1)
    additional_instructions: str = ""


# ── Generated ILAW plan (mirror of the FE GeneratedLessonPlan type) ──────────────
class LessonInformation(_CamelModel):
    """The full-width "Lesson Information" header block of the plan."""

    title: str
    learning_areas: str
    teacher_name: str
    grade_level_and_section: str
    sessions_label: str
    references: list[str]
    ai_declaration: str


class SessionObjective(_CamelModel):
    """A single Learning Objective cell: the Knowledge / Skill / Task triad."""

    knowledge: str
    skill: str
    task: str


class FlowStep(_CamelModel):
    """One numbered step within a session's Flow / Daloy ng Aralin."""

    title: str
    details: str


class Signatories(_CamelModel):
    """Prepared/checked/noted-by footer block."""

    prepared_by: str
    checked_by: str
    noted_by: str


class GeneratedLessonPlan(_CamelModel):
    """A fully-structured ILAW lesson plan.

    Lesson-wide fields are single values / flat lists; per-session fields are
    arrays whose length equals the number of sessions (``field[i]`` is Session
    ``i + 1``). Validated against the provider's JSON output, then stored verbatim.
    """

    lesson_information: LessonInformation
    learning_competency: list[str]
    learner_context: str
    session_labels: list[str]
    learning_objectives: list[list[SessionObjective]]
    pre_lesson: list[str]
    flow: list[list[FlowStep]]
    learning_resources: list[list[str]]
    opportunities_for_integration: list[list[str]]
    formative_assessment: list[str]
    extended_learning_opportunities: list[str]
    reflections: list[str]
    signatories: Signatories


# ── Persisted-record responses ───────────────────────────────────────────────────
class LessonPlanSummary(_CamelModel):
    """List-row view of a saved plan (dashboard cards).

    Inputs: hydrated from a ``LessonPlan`` ORM row (``from_attributes``).
    Outputs: camelCase JSON in the ``GET /lesson-plans`` list.
    Side effects: none.
    """

    id: uuid.UUID
    created_at: datetime
    title: str
    learning_areas: str
    grade_level_and_section: str
    sessions_label: str
    provider_used: ProviderId
    # Count of "[Teacher to complete]" cells across the plan (drives the
    # dashboard "N placeholders need your input" badge).
    placeholder_count: int


class LessonPlanDetail(_CamelModel):
    """Full view of a saved plan — returned by generate and by the detail GET.

    Inputs: assembled by the service from a ``LessonPlan`` row (``plan`` parsed
    back from the stored ``plan_json``).
    Outputs: camelCase JSON the FE renders via ``StepResult`` (reads ``plan``) and
    keys by ``id``.
    Side effects: none.
    """

    id: uuid.UUID
    created_at: datetime
    provider_used: ProviderId
    plan: GeneratedLessonPlan

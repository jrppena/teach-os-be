"""Lesson-plans domain service.

Orchestrates generation and persistence of ILAW lesson plans:

1. resolve the user's active provider + decrypted key (from the settings domain),
2. build the system/user messages from ``prompts.py``,
3. call the provider over httpx (``providers.generate_json``),
4. validate the returned JSON against ``GeneratedLessonPlan``,
5. enforce the deterministic header/signatory/label/reflection fields from the
   request (so the saved plan is faithful regardless of model drift),
6. persist a ``lesson_plan`` row and return the saved record.

Plus read/delete helpers for the dashboard history. All DB access is SQLAlchemy
2.0 async.
"""

import io
import uuid
from collections.abc import Callable
from functools import partial
from typing import TypeVar

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from src.exceptions import AppException
from src.lesson_plans import providers
from src.lesson_plans.docx_export import SchoolHeader, build_lesson_plan_docx, docx_filename
from src.lesson_plans.exceptions import NoProviderKeyConfigured, ProviderResponseError
from src.lesson_plans.models import LessonPlan
from src.lesson_plans.pdf_export import build_lesson_plan_pdf, pdf_filename
from src.lesson_plans.prompts import (
    LESSON_PLAN_JSON_SCHEMA,
    LESSON_PLAN_SYSTEM_PROMPT,
    TEACHER_TODO_PREFIX,
    LessonPlanInputs,
    build_lesson_plan_user_message,
)
from src.lesson_plans.schemas import (
    FlowStep,
    GeneratedLessonPlan,
    LessonInformation,
    LessonPlanDetail,
    LessonPlanGenerateRequest,
    LessonPlanSummary,
    SessionObjective,
    Signatories,
)
from src.settings import service as settings_service
from src.settings.schemas import ProviderId
from src.users.models import User


def _build_inputs(request: LessonPlanGenerateRequest) -> LessonPlanInputs:
    """Map the validated request to the snake_case prompt-builder input dict."""
    return LessonPlanInputs(
        lesson_title=request.lesson_title,
        grade_level=request.grade_level,
        learning_area=request.learning_area,
        term=request.term,
        week=request.week,
        teacher_name=request.teacher_name,
        section=request.section,
        sessions=request.sessions,
        minutes_per_session=request.minutes_per_session,
        references=request.references,
        ai_declaration=request.ai_declaration,
        competencies=request.competencies,
        additional_instructions=request.additional_instructions,
    )


_T = TypeVar("_T")


def _fit(items: list[_T], n: int, filler: Callable[[], _T]) -> list[_T]:
    """Truncate or pad ``items`` to exactly length ``n`` (padding via ``filler``)."""
    fitted = list(items[:n])
    while len(fitted) < n:
        fitted.append(filler())
    return fitted


def _enforce_deterministic_fields(
    plan: GeneratedLessonPlan, request: LessonPlanGenerateRequest
) -> GeneratedLessonPlan:
    """Override deterministic fields and size per-session arrays to the request.

    The provider authors the pedagogical content; this guarantees the header,
    signatories, session labels, reflection placeholders, and per-session array
    lengths are correct regardless of how faithfully the model followed the prompt.
    """
    n = request.sessions
    minutes = request.minutes_per_session

    title = request.lesson_title.strip() or f"{TEACHER_TODO_PREFIX} Lesson title"
    teacher = request.teacher_name.strip()
    section = request.section.strip()
    grade = request.grade_level.strip()
    grade_level_and_section = f"{grade} — {section}" if section else grade
    sessions_label = f"{n} session{'s' if n != 1 else ''} ({minutes} minutes each)"

    competency = plan.learning_competency or [c.strip() for c in request.competencies if c.strip()]

    reflections: list[str] = []
    for i in range(n):
        existing = plan.reflections[i].strip() if i < len(plan.reflections) else ""
        if existing.startswith(TEACHER_TODO_PREFIX):
            reflections.append(existing)
        else:
            reflections.append(
                f"{TEACHER_TODO_PREFIX} Reflect on Session {i + 1} after teaching: "
                "what worked, what to adjust next time, and any follow-up for learners."
            )

    todo = f"{TEACHER_TODO_PREFIX} Complete this section."
    return plan.model_copy(
        update={
            "lesson_information": LessonInformation(
                title=title,
                learning_areas=request.learning_area.strip(),
                teacher_name=teacher or f"{TEACHER_TODO_PREFIX} Name of teacher/s",
                grade_level_and_section=grade_level_and_section,
                sessions_label=sessions_label,
                references=[r.strip() for r in request.references if r.strip()],
                ai_declaration=request.ai_declaration.strip(),
            ),
            "learning_competency": competency,
            "session_labels": [f"Session {i + 1}" for i in range(n)],
            "signatories": Signatories(prepared_by=teacher, checked_by="", noted_by=""),
            "reflections": reflections,
            "learning_objectives": _fit(
                plan.learning_objectives,
                n,
                lambda: [SessionObjective(knowledge=todo, skill=todo, task=todo)],
            ),
            "pre_lesson": _fit(plan.pre_lesson, n, lambda: todo),
            "flow": _fit(plan.flow, n, lambda: [FlowStep(title="", details=todo)]),
            "learning_resources": _fit(plan.learning_resources, n, lambda: [todo]),
            "opportunities_for_integration": _fit(
                plan.opportunities_for_integration, n, lambda: [todo]
            ),
            "formative_assessment": _fit(plan.formative_assessment, n, lambda: todo),
            "extended_learning_opportunities": _fit(
                plan.extended_learning_opportunities, n, lambda: todo
            ),
        }
    )


def _count_placeholders(plan: GeneratedLessonPlan) -> int:
    """Count every ``[Teacher to complete]`` cell anywhere in the plan.

    Walks the dumped plan recursively and tallies string values that begin with
    the teacher-to-complete prefix (reflections, plus any field that fell back to
    a placeholder). Drives the dashboard "N placeholders need your input" badge.
    """

    def walk(value: object) -> int:
        if isinstance(value, str):
            return 1 if value.lstrip().startswith(TEACHER_TODO_PREFIX) else 0
        if isinstance(value, dict):
            return sum(walk(v) for v in value.values())
        if isinstance(value, list):
            return sum(walk(v) for v in value)
        return 0

    return walk(plan.model_dump())


def _to_detail(row: LessonPlan) -> LessonPlanDetail:
    """Build a ``LessonPlanDetail`` from a persisted row (parses ``plan_json``)."""
    return LessonPlanDetail(
        id=row.id,
        created_at=row.created_at,
        provider_used=ProviderId(row.provider_used),
        plan=GeneratedLessonPlan.model_validate(row.plan_json),
    )


async def generate_and_save(
    db: AsyncSession, user: User, request: LessonPlanGenerateRequest
) -> LessonPlanDetail:
    """Generate an ILAW plan via the user's active provider and persist it.

    Inputs: an async session, the resolved DB ``User``, and the wizard request.
    Outputs: the saved ``LessonPlanDetail`` (full plan + id + createdAt).
    Side effects: one provider HTTP call; inserts a ``lesson_plan`` row; commits.
    Raises ``NoProviderKeyConfigured`` (409) when the active provider has no key,
    and ``ProviderResponseError`` (502) when the model output fails validation.
    """
    provider, api_key = await settings_service.get_active_provider_key(db, user.id)
    if api_key is None:
        raise NoProviderKeyConfigured(provider.value)

    user_message = build_lesson_plan_user_message(_build_inputs(request))
    raw = await providers.generate_json(
        provider, api_key, LESSON_PLAN_SYSTEM_PROMPT, user_message, LESSON_PLAN_JSON_SCHEMA
    )

    try:
        plan = GeneratedLessonPlan.model_validate(raw)
    except ValidationError as exc:
        raise ProviderResponseError(
            "The AI provider's response did not match the lesson-plan format. Please try again."
        ) from exc

    plan = _enforce_deterministic_fields(plan, request)

    row = LessonPlan(
        user_id=user.id,
        title=plan.lesson_information.title,
        learning_areas=plan.lesson_information.learning_areas,
        grade_level_and_section=plan.lesson_information.grade_level_and_section,
        sessions_label=plan.lesson_information.sessions_label,
        sessions=request.sessions,
        placeholder_count=_count_placeholders(plan),
        provider_used=provider.value,
        plan_json=plan.model_dump(by_alias=True),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_detail(row)


async def list_plans(db: AsyncSession, user_id: uuid.UUID) -> list[LessonPlanSummary]:
    """Return the user's saved plans as summaries, newest first.

    Side effects: one read-only query.
    """
    rows = (
        (
            await db.execute(
                select(LessonPlan)
                .where(LessonPlan.user_id == user_id)
                .order_by(LessonPlan.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [LessonPlanSummary.model_validate(row) for row in rows]


async def get_plan(db: AsyncSession, user_id: uuid.UUID, plan_id: uuid.UUID) -> LessonPlanDetail:
    """Fetch one saved plan owned by the user.

    Side effects: one read-only query; raises 404 when missing or not owned.
    """
    row = await db.scalar(
        select(LessonPlan).where(LessonPlan.id == plan_id, LessonPlan.user_id == user_id)
    )
    if row is None:
        raise AppException(status_code=404, detail="Lesson plan not found.")
    return _to_detail(row)


async def delete_plan(db: AsyncSession, user_id: uuid.UUID, plan_id: uuid.UUID) -> None:
    """Delete one saved plan owned by the user.

    Side effects: deletes a ``lesson_plan`` row and commits; raises 404 when missing
    or not owned.
    """
    row = await db.scalar(
        select(LessonPlan).where(LessonPlan.id == plan_id, LessonPlan.user_id == user_id)
    )
    if row is None:
        raise AppException(status_code=404, detail="Lesson plan not found.")
    await db.delete(row)
    await db.commit()


async def _load_school_header(db: AsyncSession, user: User, plan_id: uuid.UUID) -> SchoolHeader:
    """Validate plan ownership and build the school header for export.

    Inputs: an async session, the authenticated ``User``, and the plan UUID.
    Outputs: a ``SchoolHeader`` populated from the user's profile fields.
    Side effects: one read-only ownership check.
    Raises ``AppException`` (404) if the plan is not found or not owned by the user.
    """
    row = await db.scalar(
        select(LessonPlan).where(LessonPlan.id == plan_id, LessonPlan.user_id == user.id)
    )
    if row is None:
        raise AppException(status_code=404, detail="Lesson plan not found.")
    return SchoolHeader(
        school_name=user.school_name,
        region=user.region,
        division=user.division,
        district=user.district,
        school_address=user.school_address,
    )


async def export_docx(
    db: AsyncSession,
    user: User,
    plan_id: uuid.UUID,
    draft: GeneratedLessonPlan,
) -> tuple[io.BytesIO, str]:
    """Validate plan ownership and build a DOCX from the provided draft.

    Inputs: an async session, the authenticated ``User``, the plan UUID for ownership
    validation, and the ``GeneratedLessonPlan`` draft (may include unsaved local edits).
    Outputs: a tuple of ``(BytesIO buffer, filename)`` ready for streaming.
    Side effects: one read-only ownership check; the DOCX builder is CPU-bound and must
    be offloaded via ``run_in_threadpool`` by the caller.
    Raises ``AppException`` (404) if the plan is not found or not owned by the user.
    """
    school = await _load_school_header(db, user, plan_id)
    buf = build_lesson_plan_docx(draft, school)
    filename = docx_filename(draft.lesson_information.title)
    return buf, filename


async def export_pdf(
    db: AsyncSession,
    user: User,
    plan_id: uuid.UUID,
    draft: GeneratedLessonPlan,
) -> tuple[io.BytesIO, str]:
    """Validate plan ownership and build a PDF from the provided draft.

    Mirrors ``export_docx`` — same ownership check, same school header population —
    but delegates to the reportlab-based ``build_lesson_plan_pdf`` builder.

    Inputs: an async session, the authenticated ``User``, the plan UUID for ownership
    validation, and the ``GeneratedLessonPlan`` draft (may include unsaved local edits).
    Outputs: a tuple of ``(BytesIO buffer, filename)`` ready for streaming.
    Side effects: one read-only ownership check; the PDF builder is CPU-bound and must
    be offloaded via ``run_in_threadpool`` by the caller.
    Raises ``AppException`` (404) if the plan is not found or not owned by the user.
    """
    school = await _load_school_header(db, user, plan_id)
    buf = await run_in_threadpool(partial(build_lesson_plan_pdf, draft, school))
    filename = pdf_filename(draft.lesson_information.title)
    return buf, filename

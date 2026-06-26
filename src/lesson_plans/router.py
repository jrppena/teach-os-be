"""Lesson-plans domain router.

Exposes the generation + history endpoints under ``/lesson-plans``:

- ``POST   /lesson-plans``       generate via the active provider and save (201)
- ``GET    /lesson-plans``       list the user's saved plans (summaries)
- ``GET    /lesson-plans/{id}``  fetch one saved plan in full
- ``DELETE /lesson-plans/{id}``  delete one saved plan (204)

All routes require a valid Firebase token resolved to the DB user via
``CurrentDbUser``.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.lesson_plans import service as lesson_plan_service
from src.lesson_plans.schemas import (
    LessonPlanDetail,
    LessonPlanGenerateRequest,
    LessonPlanSummary,
)
from src.users.dependencies import CurrentDbUser

router = APIRouter(prefix="/lesson-plans", tags=["lesson-plans"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_401 = {status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid Firebase token"}}
_404 = {status.HTTP_404_NOT_FOUND: {"description": "User or lesson plan not found"}}
_409 = {status.HTTP_409_CONFLICT: {"description": "No API key configured for the active provider"}}
_502 = {
    status.HTTP_502_BAD_GATEWAY: {
        "description": "The AI provider failed or returned an invalid response"
    }
}


@router.post(
    "",
    response_model=LessonPlanDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and save an ILAW lesson plan",
    description=(
        "Generates a DepEd MATATAG / ILAW lesson plan using the authenticated "
        "user's active AI provider (Gemini or Grok) and stored key, then persists "
        "and returns it. Requires that a key is configured for the active provider."
    ),
    responses={**_401, **_404, **_409, **_502},
)
async def generate_lesson_plan(
    payload: LessonPlanGenerateRequest,
    current_db_user: CurrentDbUser,
    db: DbSession,
) -> LessonPlanDetail:
    """Generate, persist, and return an ILAW lesson plan for the current user.

    Inputs: the wizard ``LessonPlanGenerateRequest``, the resolved DB ``User``, and
    an async DB session.
    Outputs: the saved ``LessonPlanDetail``.
    Side effects: one provider HTTP call; inserts a ``lesson_plan`` row; commits.
    """
    return await lesson_plan_service.generate_and_save(db, current_db_user, payload)


@router.get(
    "",
    response_model=list[LessonPlanSummary],
    summary="List the user's saved lesson plans",
    description="Returns the authenticated user's saved plans as summaries, newest first.",
    responses={**_401, **_404},
)
async def list_lesson_plans(
    current_db_user: CurrentDbUser,
    db: DbSession,
) -> list[LessonPlanSummary]:
    """Return the current user's saved lesson plans (summaries, newest first).

    Side effects: one read-only DB query.
    """
    return await lesson_plan_service.list_plans(db, current_db_user.id)


@router.get(
    "/{plan_id}",
    response_model=LessonPlanDetail,
    summary="Get one saved lesson plan",
    description="Returns the full saved plan if it exists and is owned by the user.",
    responses={**_401, **_404},
)
async def get_lesson_plan(
    plan_id: uuid.UUID,
    current_db_user: CurrentDbUser,
    db: DbSession,
) -> LessonPlanDetail:
    """Return one saved lesson plan owned by the current user.

    Side effects: one read-only DB query; 404 when missing or not owned.
    """
    return await lesson_plan_service.get_plan(db, current_db_user.id, plan_id)


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one saved lesson plan",
    description="Deletes the plan if it exists and is owned by the user.",
    responses={**_401, **_404},
)
async def delete_lesson_plan(
    plan_id: uuid.UUID,
    current_db_user: CurrentDbUser,
    db: DbSession,
) -> None:
    """Delete one saved lesson plan owned by the current user.

    Side effects: deletes a ``lesson_plan`` row and commits; 404 when missing or
    not owned.
    """
    await lesson_plan_service.delete_plan(db, current_db_user.id, plan_id)

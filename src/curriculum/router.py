"""Curriculum domain router.

Read-only endpoints that serve DepEd grade levels and their subjects so the FE
can populate the lesson-plan grade/subject dropdowns from the DB. Mounted under
``/api/v1`` in ``src/main.py``. Protected with ``CurrentUser`` for consistency with
the rest of the API (the generate page is always authenticated).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import CurrentUser
from src.curriculum import service as curriculum_service
from src.curriculum.schemas import GradeLevelResponse, SubjectResponse
from src.database import get_db

router = APIRouter(prefix="/curriculum", tags=["curriculum"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_401 = {status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid Firebase token"}}
_404 = {status.HTTP_404_NOT_FOUND: {"description": "Grade level not found"}}


@router.get(
    "/grade-levels",
    response_model=list[GradeLevelResponse],
    summary="List grade levels",
    description=(
        "Returns all DepEd grade levels (Grade 1-12) ordered for display. Used by the "
        "FE to populate the lesson-plan Grade Level dropdown."
    ),
    responses={**_401},
)
async def list_grade_levels(
    current_user: CurrentUser,
    db: DbSession,
) -> list[GradeLevelResponse]:
    """List all grade levels.

    Inputs: the authenticated user (token) and an async session.
    Outputs: ordered list of ``GradeLevelResponse``.
    Side effects: one read-only query.
    """
    grade_levels = await curriculum_service.list_grade_levels(db)
    return [GradeLevelResponse.model_validate(gl) for gl in grade_levels]


@router.get(
    "/grade-levels/{code}/subjects",
    response_model=list[SubjectResponse],
    summary="List a grade level's subjects",
    description=(
        "Returns the subjects for one grade level (by its stable code, e.g. GRADE_7). "
        "MATATAG core subjects for Grades 1-10; the Strengthened SHS five core subjects "
        "plus elective subjects grouped by track and cluster for Grades 11-12. Each "
        "elective row includes a nested ``cluster`` object for frontend grouping."
    ),
    responses={**_401, **_404},
)
async def list_subjects(
    code: str,
    current_user: CurrentUser,
    db: DbSession,
) -> list[SubjectResponse]:
    """List the subjects for a grade level identified by ``code``.

    Inputs: the grade ``code`` path param, the authenticated user, and a session.
    Outputs: ordered list of ``SubjectResponse`` — core subjects first, then electives
    ordered by cluster ``order_index`` then subject ``order_index``.
    Side effects: read-only queries. Raises 404 if the code is unknown.
    """
    grade_level = await curriculum_service.get_grade_level_by_code(db, code)
    if grade_level is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grade level not found")

    subjects = await curriculum_service.list_subjects(db, grade_level.id)
    return [SubjectResponse.model_validate(s) for s in subjects]

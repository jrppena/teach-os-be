"""Feedback domain router.

Exposes ``POST /feedback`` — authenticated teachers submit product feedback,
which is persisted to the ``feedback`` table linked to their user row.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.feedback import service as feedback_service
from src.feedback.schemas import FeedbackCreate, FeedbackResponse
from src.users.dependencies import CurrentDbUser

router = APIRouter(prefix="/feedback", tags=["feedback"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_401 = {status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid Firebase token"}}
_404 = {status.HTTP_404_NOT_FOUND: {"description": "User not found in database"}}


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit product feedback",
    description=(
        "Stores a feedback submission (category, optional 1–5 rating, message) "
        "authored by the authenticated teacher. Returns the created record."
    ),
    responses={**_401, **_404},
)
async def submit_feedback(
    payload: FeedbackCreate,
    current_db_user: CurrentDbUser,
    db: DbSession,
) -> FeedbackResponse:
    """Persist a feedback submission for the authenticated user.

    Inputs: a validated ``FeedbackCreate`` body, the resolved DB ``User`` (via
    ``CurrentDbUser``), and an async DB session.
    Outputs: the created ``FeedbackResponse``.
    Side effects: inserts one ``feedback`` row and commits.
    """
    feedback = await feedback_service.create_feedback(db, current_db_user.id, payload)
    return FeedbackResponse.model_validate(feedback)

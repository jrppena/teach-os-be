from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import CurrentUser
from src.database import get_db
from src.users import service as user_service
from src.users.schemas import RegisterInput, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_401 = {status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid Firebase token"}}
_403 = {status.HTTP_403_FORBIDDEN:    {"description": "Token UID does not match requested UID"}}
_404 = {status.HTTP_404_NOT_FOUND:    {"description": "User not found in database"}}
_409 = {status.HTTP_409_CONFLICT:     {"description": "User already exists"}}


@router.get(
    "/user/{firebase_uid}",
    response_model=UserResponse,
    summary="Get user by Firebase UID",
    description=(
        "Called by the FE getUser() after login. "
        "Token UID must match the path UID — users cannot fetch each other's profiles."
    ),
    responses={**_401, **_403, **_404},
)
async def get_user_by_uid(
    firebase_uid: str,
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    if current_user.uid != firebase_uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    db_user = await user_service.get_by_firebase_uid(db, firebase_uid)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await user_service.touch_last_login(db, db_user)
    return UserResponse.model_validate(db_user)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Called by the FE after createUserWithEmailAndPassword. "
        "Creates the local PostgreSQL row. Idempotent — returns existing user if already registered."
    ),
    responses={**_401, **_403},
)
async def register(
    payload: RegisterInput,
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    if current_user.uid != payload.firebaseUID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    existing = await user_service.get_by_firebase_uid(db, payload.firebaseUID)
    if existing:
        return UserResponse.model_validate(existing)

    db_user = await user_service.create_user(db, payload)
    return UserResponse.model_validate(db_user)
"""Users domain service.

Async data-access helpers for the ``user`` table, consumed by the auth endpoints
in ``src/auth/router.py``. SQLAlchemy 2.0 async only — no blocking/sync sessions.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.models import User
from src.users.schemas import OnboardingStep, RegisterInput, UpdateProfileInput


async def get_by_firebase_uid(db: AsyncSession, firebase_uid: str) -> User | None:
    """Fetch a user by their Firebase UID.

    Inputs: an async session and the Firebase UID.
    Outputs: the matching ``User`` or ``None`` if not registered locally.
    Side effects: read-only query.
    """
    result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, payload: RegisterInput) -> User:
    """Insert a new user row from a validated register payload.

    Inputs: an async session and a ``RegisterInput`` (caller has verified the
    token UID matches ``payload.firebaseUID``).
    Outputs: the persisted, refreshed ``User``.
    Side effects: inserts one row and commits.
    """
    user = User(
        firebase_uid=payload.firebaseUID,
        email=payload.email,
        first_name=payload.firstName,
        last_name=payload.lastName,
        role=payload.role.value,
        bio=payload.bio,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_profile(db: AsyncSession, user: User, patch: UpdateProfileInput) -> User:
    """Partially update a user's school profile fields.

    Inputs: an async session, the persisted ``User``, and an ``UpdateProfileInput``
    (only non-None fields are applied).
    Outputs: the refreshed ``User``.
    Side effects: updates the row and commits.
    """
    for field, value in patch.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


async def update_onboarding_step(db: AsyncSession, user: User, step: OnboardingStep) -> User:
    """Set a user's current onboarding step.

    Inputs: an async session, the persisted ``User``, and the new
    ``OnboardingStep`` (e.g. the wizard's next step, or ``COMPLETED``).
    Outputs: the refreshed ``User``.
    Side effects: updates the row and commits.
    """
    user.onboarding_step = step.value
    await db.commit()
    await db.refresh(user)
    return user


async def touch_last_login(db: AsyncSession, user: User) -> None:
    """Update a user's ``last_login`` to now.

    Inputs: an async session and the persisted ``User``.
    Outputs: none.
    Side effects: updates one row and commits.
    """
    user.last_login = datetime.now(UTC)
    await db.commit()

"""Users domain dependencies.

Provides a reusable FastAPI dependency that resolves the authenticated Firebase
user to the corresponding DB ``User`` row. Chainable by other domains (e.g.
``src/settings/``) that need the internal UUID, not just the Firebase UID.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import CurrentUser
from src.database import get_db
from src.users import service as user_service
from src.users.models import User


async def get_current_db_user(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the authenticated Firebase user to the local DB ``User`` row.

    Inputs: the verified ``FirebaseUser`` token claims and an async DB session.
    Outputs: the persisted ``User`` ORM instance.
    Side effects: raises ``404`` when no local row matches the Firebase UID.
    """
    db_user = await user_service.get_by_firebase_uid(db, current_user.uid)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please register first.",
        )
    return db_user


# Reusable type alias — use this on any protected route that needs the DB user.
CurrentDbUser = Annotated[User, Depends(get_current_db_user)]

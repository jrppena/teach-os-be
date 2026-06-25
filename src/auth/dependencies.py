from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from firebase_admin.auth import (
    ExpiredIdTokenError,
    InvalidIdTokenError,
    RevokedIdTokenError,
    UserDisabledError,
)

from src.auth.schemas import FirebaseUser

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(_bearer)],
) -> FirebaseUser:
    """Verify Firebase ID token and return the decoded user payload.

    Raises specific 401 errors per token failure mode — no bare Exception catch.
    """
    try:
        decoded = firebase_auth.verify_id_token(credentials.credentials)
    except ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
        )
    except RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please sign in again.",
        )
    except UserDisabledError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account has been disabled.",
        )
    except InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    return FirebaseUser(
        uid=decoded["uid"],
        email=decoded.get("email"),
        name=decoded.get("name"),
        email_verified=decoded.get("email_verified", False),
    )


# Reusable type alias — use this in every protected route
CurrentUser = Annotated[FirebaseUser, Depends(get_current_user)]
"""Settings domain router.

Exposes ``GET /settings/provider-keys`` and ``PATCH /settings/provider-keys``.
Keys are write-only from the client's perspective — GET returns a masked preview
plus a ``configured`` flag, never the raw key.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.settings import service as settings_service
from src.settings.schemas import ProviderKeysResponse, ProviderKeysUpdate
from src.users.dependencies import CurrentDbUser

router = APIRouter(prefix="/settings", tags=["settings"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_401 = {status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid Firebase token"}}
_404 = {status.HTTP_404_NOT_FOUND: {"description": "User not found in database"}}


@router.get(
    "/provider-keys",
    response_model=ProviderKeysResponse,
    summary="Get provider key status (masked)",
    description=(
        "Returns the active provider and a masked key preview (never the raw key) "
        "for each supported provider. ``configured: false`` when no key is stored."
    ),
    responses={**_401, **_404},
)
async def get_provider_keys(
    current_db_user: CurrentDbUser,
    db: DbSession,
) -> ProviderKeysResponse:
    """Return the masked provider-key status for the authenticated user.

    Inputs: the resolved DB ``User`` (via ``CurrentDbUser``) and an async DB session.
    Outputs: ``ProviderKeysResponse`` with ``configured``/``preview`` per provider.
    Side effects: two read-only DB queries.
    """
    return await settings_service.get_provider_keys(db, current_db_user.id)


@router.patch(
    "/provider-keys",
    response_model=ProviderKeysResponse,
    summary="Update provider keys (partial)",
    description=(
        "Partial update: ``activeProvider`` switches the active provider; "
        "``keys`` is a provider→value map where a non-empty value upserts the "
        "key and an empty string ``\"\"`` clears it. Omitted providers are unchanged."
    ),
    responses={**_401, **_404},
)
async def update_provider_keys(
    payload: ProviderKeysUpdate,
    current_db_user: CurrentDbUser,
    db: DbSession,
) -> ProviderKeysResponse:
    """Apply a partial update to provider settings for the authenticated user.

    Inputs: a ``ProviderKeysUpdate`` body, the resolved DB ``User``, and an async
    DB session.
    Outputs: the refreshed masked ``ProviderKeysResponse``.
    Side effects: upserts/deletes ``provider_key`` rows and upserts
    ``provider_setting``; commits.
    """
    return await settings_service.update_provider_keys(db, current_db_user.id, payload)

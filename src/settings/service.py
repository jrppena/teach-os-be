"""Settings domain service.

Async data-access helpers for the ``provider_setting`` and ``provider_key``
tables. All DB operations use SQLAlchemy 2.0 async — no blocking sessions.
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.settings.models import ProviderKey, ProviderSetting
from src.settings.schemas import (
    ProviderId,
    ProviderKeyStatus,
    ProviderKeysResponse,
    ProviderKeysUpdate,
)
from src.settings.utils import decrypt, encrypt, mask


async def get_provider_keys(db: AsyncSession, user_id: uuid.UUID) -> ProviderKeysResponse:
    """Read the provider settings and keys for a user, returning a masked response.

    Inputs: an async session and the internal user UUID.
    Outputs: ``ProviderKeysResponse`` with ``configured``/masked ``preview`` per
    provider; never exposes the raw key.
    Side effects: two read-only queries.
    """
    setting_row = await db.scalar(
        select(ProviderSetting).where(ProviderSetting.user_id == user_id)
    )
    active_provider = ProviderId(setting_row.active_provider) if setting_row else ProviderId.GEMINI

    key_rows = (
        await db.execute(select(ProviderKey).where(ProviderKey.user_id == user_id))
    ).scalars().all()

    key_map: dict[str, ProviderKey] = {row.provider: row for row in key_rows}

    keys: dict[ProviderId, ProviderKeyStatus] = {}
    for provider in ProviderId:
        row = key_map.get(provider.value)
        if row:
            plaintext = decrypt(row.encrypted_key)
            keys[provider] = ProviderKeyStatus(configured=True, preview=mask(plaintext))
        else:
            keys[provider] = ProviderKeyStatus(configured=False, preview=None)

    return ProviderKeysResponse(active_provider=active_provider, keys=keys)


async def update_provider_keys(
    db: AsyncSession,
    user_id: uuid.UUID,
    payload: ProviderKeysUpdate,
) -> ProviderKeysResponse:
    """Apply a partial update to the provider settings and keys for a user.

    Inputs: an async session, the internal user UUID, and a ``ProviderKeysUpdate``
    payload (all fields optional).
    Outputs: the refreshed masked ``ProviderKeysResponse`` after applying changes.
    Side effects: upserts ``provider_setting`` and zero or more ``provider_key``
    rows; may delete key rows; commits the session.
    """
    active = payload.active_provider.value if payload.active_provider is not None else ProviderId.GEMINI.value
    setting_row = await db.scalar(
        select(ProviderSetting).where(ProviderSetting.user_id == user_id)
    )
    if setting_row is None:
        db.add(ProviderSetting(user_id=user_id, active_provider=active))
    else:
        setting_row.active_provider = active

    if payload.keys:
        for provider, raw_value in payload.keys.items():
            trimmed = raw_value.strip()
            if trimmed:
                ciphertext = encrypt(trimmed)
                stmt = (
                    insert(ProviderKey)
                    .values(
                        user_id=user_id,
                        provider=provider.value,
                        encrypted_key=ciphertext,
                    )
                    .on_conflict_do_update(
                        constraint="provider_key_user_id_provider_key",
                        set_={"encrypted_key": ciphertext},
                    )
                )
                await db.execute(stmt)
            else:
                await db.execute(
                    delete(ProviderKey).where(
                        ProviderKey.user_id == user_id,
                        ProviderKey.provider == provider.value,
                    )
                )

    await db.commit()
    return await get_provider_keys(db, user_id)

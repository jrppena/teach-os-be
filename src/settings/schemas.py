"""Settings domain schemas.

Pydantic v2 request/response models for the provider-key endpoints. Uses the
same camelCase alias generator and ``_CamelModel`` base as ``src/users/schemas.py``
so the FE receives camelCase JSON while the DB stays snake_case.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ProviderId(StrEnum):
    """Supported AI provider identifiers. Mirrors the FE ``ProviderId`` union."""

    GEMINI = "gemini"
    GROK = "grok"


class _CamelModel(BaseModel):
    """Base config: emit/accept camelCase, also accept field names, read from ORM."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ProviderKeyStatus(_CamelModel):
    """Masked status for a single provider.

    Inputs: built from a ``ProviderKey`` row (configured=True) or synthesised
    (configured=False, preview=None) when no row exists for this provider.
    Outputs: embedded in ``ProviderKeysResponse``.
    Side effects: none.
    """

    configured: bool
    preview: str | None


class ProviderKeysResponse(_CamelModel):
    """Response body for GET and PATCH ``/settings/provider-keys``.

    Inputs: assembled by ``settings_service.get_provider_keys``.
    Outputs: camelCase JSON — e.g.::

        {
          "activeProvider": "gemini",
          "keys": {
            "gemini": {"configured": true, "preview": "••••1a2b"},
            "grok":   {"configured": false, "preview": null}
          }
        }

    Side effects: none. The ``preview`` field is masked; raw keys are never
    returned.
    """

    active_provider: ProviderId
    keys: dict[ProviderId, ProviderKeyStatus]


class ProviderKeysUpdate(_CamelModel):
    """PATCH body for ``/settings/provider-keys``.

    All fields optional — a partial map. For each entry in ``keys``:
    - Non-empty (trimmed) value → encrypt and upsert.
    - Empty string ``""`` → delete the provider's key row.
    - Provider omitted → left unchanged.

    Inputs: camelCase JSON body from the FE.
    Outputs: consumed by ``settings_service.update_provider_keys``.
    Side effects: none at schema level.
    """

    active_provider: ProviderId | None = None
    keys: dict[ProviderId, str] | None = None

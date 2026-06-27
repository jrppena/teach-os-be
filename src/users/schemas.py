"""Users domain schemas.

Request/response models for the auth endpoints. The frontend speaks camelCase
(see teacher-os-fe ``src/types/api.ts``) while the DB is snake_case, so these
models use a camelCase alias generator and accept/emit camelCase JSON while still
populating from snake_case ORM attributes.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, field_serializer
from pydantic.alias_generators import to_camel


class UserRole(StrEnum):
    """Allowed user roles. Mirrors the FE ``User['role']`` union."""

    USER = "USER"
    ADMIN = "ADMIN"


class _CamelModel(BaseModel):
    """Base config: emit/accept camelCase, also accept field names, read from ORM."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class RegisterInput(_CamelModel):
    """Body for ``POST /auth/register``.

    Sent by the FE right after ``createUserWithEmailAndPassword``. ``firebaseUID``
    must match the verified token UID (enforced in the router). ``role``/``bio``
    have defaults so the FE may omit them.

    Inputs: camelCase JSON body.
    Outputs: validated object consumed by ``user_service.create_user``.
    Side effects: none.
    """

    # Explicit attribute name to match ``payload.firebaseUID`` in the router; the
    # camel alias generator maps it to the JSON key ``firebaseUID`` unchanged.
    firebaseUID: str
    email: EmailStr
    firstName: str
    lastName: str
    role: UserRole = UserRole.USER
    bio: str = ""


class UserResponse(_CamelModel):
    """Response model for the auth endpoints — the FE ``User`` shape.

    Inputs: validated from a ``User`` ORM instance (``from_attributes``).
    Outputs: camelCase JSON (aliases via ``to_camel``) with ``createdAt`` as ISO-8601.
    Side effects: none.

    Fields are snake_case to match ORM attributes; ``to_camel`` generates the JSON aliases.
    """

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    role: UserRole
    bio: str
    school_name: str
    region: str
    division: str
    district: str
    school_address: str
    created_at: datetime

    @field_serializer("id", when_used="json")
    def _serialize_id(self, value: uuid.UUID) -> str:
        # ``id`` is a UUID on the ORM model; emit it as a plain string for the FE.
        return str(value)

    @field_serializer("created_at", when_used="json")
    def _serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()


class UpdateProfileInput(_CamelModel):
    """Body for ``PATCH /auth/user`` — partial update of the teacher's profile.

    All fields are optional; only provided fields are written to the DB. Primarily
    used to store DepEd school header information for DOCX export.

    Inputs: camelCase JSON body (fields omitted are left unchanged).
    Outputs: consumed by ``user_service.update_profile``.
    Side effects: none at schema level.
    """

    school_name: str | None = None
    region: str | None = None
    division: str | None = None
    district: str | None = None
    school_address: str | None = None

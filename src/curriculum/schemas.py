"""Curriculum domain schemas.

camelCase response models for the ``/curriculum`` endpoints. The FE speaks
camelCase while the DB/ORM is snake_case, so these mirror the ``_CamelModel``
pattern used in ``src/users/schemas.py`` (alias generator + read-from-ORM).
"""

import uuid

from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel

from src.curriculum.constants import Curriculum, SubjectCategory, Track


class _CamelModel(BaseModel):
    """Base config: emit/accept camelCase, also accept field names, read from ORM."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class GradeLevelResponse(_CamelModel):
    """Response row for ``GET /curriculum/grade-levels``.

    Inputs: validated from a ``GradeLevel`` ORM instance (``from_attributes``).
    Outputs: camelCase JSON; ``id`` serialized as a plain string.
    Side effects: none.
    """

    id: uuid.UUID
    code: str
    name: str
    curriculum: Curriculum
    order_index: int

    @field_serializer("id", when_used="json")
    def _serialize_id(self, value: uuid.UUID) -> str:
        return str(value)


class ClusterResponse(_CamelModel):
    """Nested cluster info included on elective ``SubjectResponse`` rows.

    Inputs: validated from a ``Cluster`` ORM instance (``from_attributes``).
    Outputs: camelCase JSON; ``id`` serialized as a plain string.
    Side effects: none.
    """

    id: uuid.UUID
    name: str
    track: Track
    order_index: int

    @field_serializer("id", when_used="json")
    def _serialize_id(self, value: uuid.UUID) -> str:
        return str(value)


class SubjectResponse(_CamelModel):
    """Response row for ``GET /curriculum/grade-levels/{code}/subjects``.

    Inputs: validated from a ``Subject`` ORM instance (``from_attributes``).
    Outputs: camelCase JSON; ``cluster`` is null for K-10 and SHS core subjects.
    Side effects: none.
    """

    id: uuid.UUID
    name: str
    category: SubjectCategory
    cluster: ClusterResponse | None
    order_index: int

    @field_serializer("id", when_used="json")
    def _serialize_id(self, value: uuid.UUID) -> str:
        return str(value)

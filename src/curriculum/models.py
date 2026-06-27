"""Curriculum domain ORM models.

Three global reference tables on the shared ``Base`` (not scoped to any user):

- ``grade_level`` — one row per DepEd grade (Grade 1 … Grade 12).
- ``cluster`` — one row per Strengthened-SHS elective cluster; carries the track
  (``ACADEMIC``/``TECHPRO``) and is shared across grade levels via the M2M.
- ``subject`` — one row per subject. A core/K-10 subject belongs to exactly one
  grade (``grade_level_id`` set, ``cluster_id`` NULL); an SHS elective belongs to
  exactly one cluster (``cluster_id`` set, ``grade_level_id`` NULL). The XOR CHECK
  on the table enforces this invariant.
- ``cluster_grade_level`` — M2M linking clusters to the grades that offer them
  (currently Grade 11 and Grade 12 for all SHS clusters).

Column/constraint names follow the Postgres naming convention in ``src/database.py``.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy import Column as SAColumn
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.curriculum.constants import SubjectCategory
from src.database import Base

# M2M association table: cluster ↔ grade_level
cluster_grade_level = Table(
    "cluster_grade_level",
    Base.metadata,
    SAColumn(
        "cluster_id",
        ForeignKey("cluster.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    SAColumn(
        "grade_level_id",
        ForeignKey("grade_level.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class GradeLevel(Base):
    """A DepEd grade level (reference data).

    Inputs: seeded by the curriculum seed migration.
    Outputs: hydrated into ``GradeLevelResponse`` for the grade-level dropdown.
    Side effects: persisted to the ``grade_level`` table.

    ``code`` is a stable, URL-safe identifier (e.g. ``GRADE_7``) used to look up a
    grade's subjects; ``order_index`` drives display ordering.
    """

    __tablename__ = "grade_level"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    curriculum: Mapped[str] = mapped_column(String(50))
    order_index: Mapped[int] = mapped_column(Integer)

    clusters: Mapped[list["Cluster"]] = relationship(
        "Cluster",
        secondary=cluster_grade_level,
        back_populates="grade_levels",
    )


class Cluster(Base):
    """A Strengthened-SHS elective cluster (reference data).

    Inputs: seeded by the data migration.
    Outputs: nested inside ``SubjectResponse.cluster`` for the subject dropdown.
    Side effects: persisted to the ``cluster`` table.

    ``track`` is ``ACADEMIC`` or ``TECHPRO``; ``order_index`` drives display ordering
    within a track. A cluster is shared across Grade 11 and Grade 12 via the
    ``cluster_grade_level`` M2M (avoids duplicating per-grade cluster rows).
    """

    __tablename__ = "cluster"
    __table_args__ = (UniqueConstraint("name", name="cluster_name_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150))
    track: Mapped[str] = mapped_column(String(20))
    order_index: Mapped[int] = mapped_column(Integer)

    grade_levels: Mapped[list[GradeLevel]] = relationship(
        GradeLevel,
        secondary=cluster_grade_level,
        back_populates="clusters",
    )
    subjects: Mapped[list["Subject"]] = relationship(
        "Subject",
        back_populates="cluster",
        passive_deletes=True,
    )


class Subject(Base):
    """A subject offered at a grade level or within a cluster (reference data).

    Inputs: seeded by the curriculum migrations.
    Outputs: hydrated into ``SubjectResponse`` for the subject dropdown.
    Side effects: persisted to the ``subject`` table; cascade-deletes with its
    parent ``grade_level`` (core) or sets ``cluster_id`` to NULL if the cluster
    is deleted (elective).

    Exactly one of ``grade_level_id`` (core/K-10) or ``cluster_id`` (elective) is
    non-NULL — enforced by the XOR CHECK constraint on the table.
    ``category`` is ``CORE`` or ``ELECTIVE``; ``order_index`` drives display ordering.
    """

    __tablename__ = "subject"
    __table_args__ = (
        UniqueConstraint("grade_level_id", "name", name="subject_grade_level_id_name_key"),
        UniqueConstraint("cluster_id", "name", name="subject_cluster_id_name_key"),
        CheckConstraint(
            "(grade_level_id IS NULL) != (cluster_id IS NULL)",
            name="subject_xor_grade_level_or_cluster_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    grade_level_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("grade_level.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cluster.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(
        String(20),
        default=SubjectCategory.CORE.value,
        server_default=SubjectCategory.CORE.value,
    )
    order_index: Mapped[int] = mapped_column(Integer)

    cluster: Mapped[Cluster | None] = relationship(
        Cluster,
        back_populates="subjects",
    )

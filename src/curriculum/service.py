"""Curriculum domain service.

Async, read-only data-access helpers for the ``grade_level``, ``cluster``, and
``subject`` reference tables, consumed by ``src/curriculum/router.py``. SQLAlchemy
2.0 async only — ordering is done in SQL so the API returns display-ready rows.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.curriculum.models import Cluster, GradeLevel, Subject, cluster_grade_level


async def list_grade_levels(db: AsyncSession) -> list[GradeLevel]:
    """Fetch all grade levels, ordered for display.

    Inputs: an async session.
    Outputs: every ``GradeLevel`` ordered by ``order_index``.
    Side effects: read-only query.
    """
    result = await db.execute(select(GradeLevel).order_by(GradeLevel.order_index))
    return list(result.scalars().all())


async def get_grade_level_by_code(db: AsyncSession, code: str) -> GradeLevel | None:
    """Fetch a single grade level by its stable ``code`` (e.g. ``GRADE_7``).

    Inputs: an async session and the grade code.
    Outputs: the matching ``GradeLevel`` or ``None``.
    Side effects: read-only query.
    """
    result = await db.execute(select(GradeLevel).where(GradeLevel.code == code))
    return result.scalar_one_or_none()


async def list_subjects(db: AsyncSession, grade_level_id: uuid.UUID) -> list[Subject]:
    """Fetch all subjects for a grade level, ordered for display.

    Returns the union of:
    - Core subjects whose ``grade_level_id`` matches directly (K-10 and SHS core).
    - Elective subjects whose parent cluster is linked to the grade via the
      ``cluster_grade_level`` M2M; ordered by cluster ``order_index`` then subject
      ``order_index`` so the FE can group by track → cluster.

    The ``cluster`` relationship is eagerly loaded on every row so callers can
    access ``subject.cluster`` without issuing additional queries.

    Inputs: an async session and the parent grade level's UUID.
    Outputs: core subjects first (ordered by ``order_index``), then elective subjects
    ordered by their cluster's ``order_index`` then their own ``order_index``.
    Side effects: read-only queries.
    """
    # Core subjects — directly attached to this grade level.
    core_stmt = (
        select(Subject)
        .where(Subject.grade_level_id == grade_level_id)
        .order_by(Subject.order_index)
        .options(selectinload(Subject.cluster))
    )

    # Elective subjects — belong to a cluster linked to this grade via M2M.
    elective_stmt = (
        select(Subject)
        .join(Cluster, Subject.cluster_id == Cluster.id)
        .join(
            cluster_grade_level,
            (cluster_grade_level.c.cluster_id == Cluster.id)
            & (cluster_grade_level.c.grade_level_id == grade_level_id),
        )
        .order_by(Cluster.order_index, Subject.order_index)
        .options(selectinload(Subject.cluster))
    )

    core_result = await db.execute(core_stmt)
    elective_result = await db.execute(elective_stmt)

    core_subjects = list(core_result.scalars().all())
    elective_subjects = list(elective_result.scalars().all())

    return core_subjects + elective_subjects

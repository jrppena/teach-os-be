"""Curriculum domain.

Read-only DepEd reference data: grade levels, clusters, and subjects
(MATATAG for Grades 1-10; the Strengthened SHS Curriculum for Grades 11-12).
Seeded via Alembic migrations and exposed through ``GET /api/v1/curriculum/*`` so
the frontend can populate the lesson-plan grade/subject dropdowns from the DB
instead of hardcoded arrays.

Schema:
- ``grade_level`` — one row per grade (Grade 1-12); ``code`` is the stable URL key.
- ``cluster`` — Strengthened-SHS elective cluster (e.g. STEM, Hospitality); carries
  ``track`` (``ACADEMIC``/``TECHPRO``) and is linked to Grade 11+12 via the M2M.
- ``cluster_grade_level`` — M2M: which grade levels offer a given cluster.
- ``subject`` — a single subject. Core/K-10 subjects have ``grade_level_id`` set;
  SHS elective subjects have ``cluster_id`` set. Exactly one is non-NULL (XOR CHECK).
"""

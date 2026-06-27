"""Curriculum domain constants.

Enumerated values shared by the models, schemas, and seed migration so the seed
data and the API agree on a single vocabulary. Stored as plain strings on the
``subject`` and ``cluster`` tables (no DB enum type) to keep migrations simple
and additive.
"""

from enum import StrEnum


class Curriculum(StrEnum):
    """Which DepEd curriculum a grade level follows (metadata on ``grade_level``)."""

    MATATAG = "MATATAG"
    STRENGTHENED_SHS = "Strengthened SHS"


class SubjectCategory(StrEnum):
    """Classification of a subject within its grade or cluster.

    ``CORE`` covers every K-10 subject and the five Strengthened-SHS core subjects;
    ``ELECTIVE`` covers the Strengthened-SHS elective subjects that belong to a cluster.
    """

    CORE = "CORE"
    ELECTIVE = "ELECTIVE"


class Track(StrEnum):
    """Strengthened SHS track for a cluster (null for K-10 + SHS core subjects)."""

    ACADEMIC = "ACADEMIC"
    TECHPRO = "TECHPRO"

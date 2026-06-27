"""seed curriculum data

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-27

Seeds the 2026 DepEd curriculum into ``grade_level`` and ``learning_area``:

- Grades 1-10 — MATATAG learning areas (the K-10 reform; subjects vary per grade).
- Grades 11-12 — Strengthened SHS Curriculum: the five core subjects plus the
  Academic and Technical-Professional (TechPro) track elective clusters. The new
  curriculum replaces the old strands with these clusters, so each cluster is
  seeded as a selectable elective learning area grouped by ``track``.

String literals (not app enums) are used so this historical migration stays valid
regardless of future code changes. ``downgrade`` clears both reference tables,
which the curriculum migrations exclusively own.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── Curriculum source data ───────────────────────────────────────────────────
# Grade levels: (code, name, curriculum). order_index follows list order.
MATATAG = "MATATAG"
STRENGTHENED_SHS = "Strengthened SHS"

_GRADES: list[tuple[str, str, str]] = [
    ("GRADE_1", "Grade 1", MATATAG),
    ("GRADE_2", "Grade 2", MATATAG),
    ("GRADE_3", "Grade 3", MATATAG),
    ("GRADE_4", "Grade 4", MATATAG),
    ("GRADE_5", "Grade 5", MATATAG),
    ("GRADE_6", "Grade 6", MATATAG),
    ("GRADE_7", "Grade 7", MATATAG),
    ("GRADE_8", "Grade 8", MATATAG),
    ("GRADE_9", "Grade 9", MATATAG),
    ("GRADE_10", "Grade 10", MATATAG),
    ("GRADE_11", "Grade 11", STRENGTHENED_SHS),
    ("GRADE_12", "Grade 12", STRENGTHENED_SHS),
]

# MATATAG learning areas per grade (all CORE, no track).
_GMRC = "Good Manners and Right Conduct (GMRC)"
_MAPEH = "Music, Arts, Physical Education & Health (MAPEH)"
_TLE = "Technology & Livelihood Education (TLE)"

_MATATAG_AREAS: dict[str, list[str]] = {
    "GRADE_1": ["Language", "Reading and Literacy", "Mathematics", _GMRC, "Makabansa"],
    "GRADE_2": ["Filipino", "English", "Mathematics", _GMRC, "Makabansa"],
    "GRADE_3": ["Filipino", "English", "Mathematics", "Science", _GMRC, "Makabansa"],
}
# Grades 4-6 share one subject set; Grades 7-10 share another.
_GRADES_4_TO_6 = ["Filipino", "English", "Mathematics", "Science", "Araling Panlipunan", _MAPEH, _GMRC, "Edukasyong Pantahanan at Pangkabuhayan / TLE (EPP/TLE)"]
_GRADES_7_TO_10 = ["Filipino", "English", "Mathematics", "Science", "Araling Panlipunan", _MAPEH, "Values Education (EsP)", _TLE]
for _g in ("GRADE_4", "GRADE_5", "GRADE_6"):
    _MATATAG_AREAS[_g] = list(_GRADES_4_TO_6)
for _g in ("GRADE_7", "GRADE_8", "GRADE_9", "GRADE_10"):
    _MATATAG_AREAS[_g] = list(_GRADES_7_TO_10)

# Strengthened SHS (Grades 11-12): five core subjects shared by both years.
_SHS_CORE = [
    "Effective Communication (Mabisang Komunikasyon)",
    "Life and Career Skills",
    "General Mathematics",
    "General Science",
    "Pag-aaral ng Kasaysayan at Lipunang Pilipino",
]
# Elective clusters by track (the reform replaced strands with these clusters).
_SHS_ACADEMIC_ELECTIVES = [
    "Arts, Social Sciences, and Humanities",
    "Business and Entrepreneurship",
    "Science, Technology, Engineering, and Mathematics (STEM)",
    "Sports, Health, and Wellness",
    "Field Experience",
]
_SHS_TECHPRO_ELECTIVES = [
    "Aesthetic, Wellness, and Human Care",
    "Agri-Fishery Business and Food Innovation",
    "Artisanry and Creative Enterprise",
    "Automotive and Small Engine Technologies",
    "Construction and Building Technology",
    "Creative Arts and Design Technology",
    "Hospitality and Tourism",
    "ICT Support and Computer Programming",
    "Industrial Technologies",
    "Maritime",
]


def _learning_areas_for(code: str, grade_id: uuid.UUID) -> list[dict]:
    """Build the learning_area insert rows for one grade level.

    Inputs: the grade ``code`` and its generated ``grade_id``.
    Outputs: a list of column dicts (CORE first, then Academic then TechPro
    electives for SHS), with ``order_index`` following insertion order.
    Side effects: none.
    """
    rows: list[dict] = []

    def _add(name: str, category: str, track: str | None) -> None:
        rows.append(
            {
                "id": uuid.uuid4(),
                "grade_level_id": grade_id,
                "name": name,
                "category": category,
                "track": track,
                "order_index": len(rows),
            }
        )

    if code in _MATATAG_AREAS:
        for name in _MATATAG_AREAS[code]:
            _add(name, "CORE", None)
    else:  # Strengthened SHS (Grades 11-12)
        for name in _SHS_CORE:
            _add(name, "CORE", None)
        for name in _SHS_ACADEMIC_ELECTIVES:
            _add(name, "ELECTIVE", "ACADEMIC")
        for name in _SHS_TECHPRO_ELECTIVES:
            _add(name, "ELECTIVE", "TECHPRO")

    return rows


def upgrade() -> None:
    grade_level_t = sa.table(
        "grade_level",
        sa.column("id", sa.Uuid),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("curriculum", sa.String),
        sa.column("order_index", sa.Integer),
    )
    learning_area_t = sa.table(
        "learning_area",
        sa.column("id", sa.Uuid),
        sa.column("grade_level_id", sa.Uuid),
        sa.column("name", sa.String),
        sa.column("category", sa.String),
        sa.column("track", sa.String),
        sa.column("order_index", sa.Integer),
    )

    grade_rows: list[dict] = []
    area_rows: list[dict] = []
    for order, (code, name, curriculum) in enumerate(_GRADES):
        grade_id = uuid.uuid4()
        grade_rows.append(
            {
                "id": grade_id,
                "code": code,
                "name": name,
                "curriculum": curriculum,
                "order_index": order,
            }
        )
        area_rows.extend(_learning_areas_for(code, grade_id))

    op.bulk_insert(grade_level_t, grade_rows)
    op.bulk_insert(learning_area_t, area_rows)


def downgrade() -> None:
    # The curriculum migrations exclusively own these tables, so clearing them is safe.
    op.execute("DELETE FROM learning_area")
    op.execute("DELETE FROM grade_level")

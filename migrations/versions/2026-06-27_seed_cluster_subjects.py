"""seed cluster and elective subject data

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-27

Replaces the old "cluster-as-learning-area" rows with the correct model:

1. Deletes the existing ELECTIVE rows from ``subject`` (previously stored cluster
   names as if they were subjects; the old seed also duplicated them per grade).
2. Inserts 15 ``cluster`` rows — 5 Academic + 10 Technical-Professional — with
   corrected names per the Strengthened SHS curriculum reference.
3. Links each cluster to both Grade 11 and Grade 12 via ``cluster_grade_level``.
4. Inserts per-cluster elective ``subject`` rows (``grade_level_id=NULL``,
   ``cluster_id`` set). Subjects are seeded once per cluster, not per grade.

Corrected cluster names vs. the old seed:
- ``ICT Support and Computer Programming``        → ``ICT Support and Computer Programming Technologies``
- ``Maritime``                                    → ``Maritime Transport``
- ``Construction and Building Technology``        → ``Construction and Building Technologies``
- ``Creative Arts and Design Technology``         → ``Creative Arts and Design Technologies``

Subject lists are compiled from DepEd's Strengthened SHS curriculum guides.
Clusters whose official CGs have not yet been released carry a small representative
set (marked "# Note: provisional" in the source).

``downgrade`` restores the old ELECTIVE rows as they were in the previous seed.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ── Track constants ─────────────────────────────────────────────────────────
ACADEMIC = "ACADEMIC"
TECHPRO = "TECHPRO"

# ── Cluster definitions: (name, track, order_index) ─────────────────────────
# Academic clusters (order 0-4)
# TechPro clusters (order 0-9)
_CLUSTERS: list[tuple[str, str, int]] = [
    # Academic
    ("Arts, Social Sciences, and Humanities", ACADEMIC, 0),
    ("Business and Entrepreneurship", ACADEMIC, 1),
    ("Science, Technology, Engineering, and Mathematics (STEM)", ACADEMIC, 2),
    ("Sports, Health, and Wellness", ACADEMIC, 3),
    ("Field Experience", ACADEMIC, 4),
    # Technical-Professional
    ("Aesthetic, Wellness, and Human Care", TECHPRO, 0),
    ("Agri-Fishery Business and Food Innovation", TECHPRO, 1),
    ("Artisanry and Creative Enterprise", TECHPRO, 2),
    ("Automotive and Small Engine Technologies", TECHPRO, 3),
    ("Construction and Building Technologies", TECHPRO, 4),
    ("Creative Arts and Design Technologies", TECHPRO, 5),
    ("Hospitality and Tourism", TECHPRO, 6),
    ("ICT Support and Computer Programming Technologies", TECHPRO, 7),
    ("Industrial Technologies", TECHPRO, 8),
    ("Maritime Transport", TECHPRO, 9),
]

# ── Elective subjects per cluster (name → list[subject_name]) ───────────────
_CLUSTER_SUBJECTS: dict[str, list[str]] = {
    # Note: provisional — official CG not yet released for this cluster.
    "Arts, Social Sciences, and Humanities": [
        "Creative Writing",
        "Creative Nonfiction",
        "Introduction to Philosophy of the Human Person",
        "Philippine Literature in English",
        "World Religions and Belief Systems",
        "Human Behavior and Society",
        "Arts Appreciation",
        "Cultural Heritage Studies",
        "Theater Arts",
        "Media Literacy and Criticism",
    ],
    # Note: provisional — official CG not yet released for this cluster.
    "Business and Entrepreneurship": [
        "Fundamentals of Business",
        "Entrepreneurship (Starting a Business)",
        "Financial Management",
        "Accounting Fundamentals",
        "Business Mathematics (Applied)",
        "E-Commerce and Digital Marketing",
        "Marketing Management",
        "Business Law",
    ],
    "Science, Technology, Engineering, and Mathematics (STEM)": [
        "Pre-Calculus 1",
        "Pre-Calculus 2",
        "Advanced Mathematics 1",
        "Advanced Mathematics 2",
        "Finite Mathematics",
        "Fundamentals of Data Analytics",
        "Biology 1",
        "Biology 2",
        "Biology 3",
        "Biology 4",
        "Chemistry 1",
        "Chemistry 2",
        "Chemistry 3",
        "Chemistry 4",
        "Physics 1",
        "Physics 2",
        "Physics 3",
        "Physics 4",
        "Earth and Space Science 1",
        "Earth and Space Science 2",
        "Earth and Space Science 3",
        "Earth and Space Science 4",
        "Database Management",
        "Empowerment Technologies",
    ],
    # Note: provisional — official CG not yet released for this cluster.
    "Sports, Health, and Wellness": [
        "Physical Fitness and Wellness",
        "Sports Science",
        "Sports Officiating and Officiating",
        "Community Sports Program Management",
        "First Aid and Emergency Care",
        "Health and Wellness Promotion",
        "Nutrition and Dietetics",
    ],
    # Note: provisional — official CG not yet released for this cluster.
    "Field Experience": [
        "Work Immersion / Practicum",
        "Industry Exposure",
        "Community Service Learning",
        "Career Exploration and Development",
    ],
    # Note: provisional — official CG not yet released for this cluster.
    "Aesthetic, Wellness, and Human Care": [
        "Beauty Care (Nail Care Technology)",
        "Beauty Care (Hair Cutting and Hair Care Services)",
        "Beauty Care (Facial Care and Body Treatments)",
        "Massage Therapy",
        "Child Development and Care",
        "Caregiving Technology",
        "Health Care Services",
    ],
    # Note: provisional — official CG not yet released for this cluster.
    "Agri-Fishery Business and Food Innovation": [
        "Crop Production",
        "Animal Production",
        "Aquaculture",
        "Food Processing",
        "Organic Farming Technology",
        "Agricultural Technology",
        "Food Innovation and Entrepreneurship",
    ],
    # Note: provisional — official CG not yet released for this cluster.
    "Artisanry and Creative Enterprise": [
        "Furniture and Cabinet Making",
        "Basket and Bag Making",
        "Pottery Making",
        "Jewelry Making",
        "Fashion Design",
        "Dressmaking / Tailoring",
        "Handicraft and Product Development",
    ],
    # Note: provisional — official CG not yet released for this cluster.
    "Automotive and Small Engine Technologies": [
        "Automotive Servicing",
        "Small Engine Repair",
        "Automotive Electrical Systems Servicing",
        "Automotive Engine Repair and Overhaul",
        "Vehicle Painting and Refinishing",
    ],
    # Note: provisional — official CG not yet released for this cluster.
    "Construction and Building Technologies": [
        "Carpentry",
        "Masonry",
        "Electrical Installation and Maintenance",
        "Plumbing",
        "Shielded Metal Arc Welding (SMAW)",
        "Tile Setting and Floor Laying",
    ],
    # Note: provisional — official CG not yet released for this cluster.
    "Creative Arts and Design Technologies": [
        "Visual Communication and Graphic Design",
        "Illustration",
        "Animation (2D/3D)",
        "Photography",
        "Film and Television Production",
        "Sound Production",
        "Game Art and Design",
    ],
    "Hospitality and Tourism": [
        "Kitchen Operations",
        "Bakery Operations",
        "Food and Beverage Operation",
        "Hotel Operation — Front-Office Services",
        "Hotel Operation — Housekeeping Services",
        "Events Management",
        "Tourism Services",
        "Hotel Services",
    ],
    "ICT Support and Computer Programming Technologies": [
        "Computer Programming (Java)",
        "Computer Programming (.NET)",
        "Computer Programming (Oracle Database)",
        "Computer Systems Servicing",
        "Visual Graphics Design",
        "Animation",
        "Illustration",
        "Technical Drafting",
        "Contact Center Services",
        "Broadband Installation (Fixed Wireless Systems)",
        "Empowerment Technologies",
    ],
    # Note: provisional — official CG not yet released for this cluster.
    "Industrial Technologies": [
        "Electronics Technology",
        "Consumer Electronics Servicing",
        "Shielded Metal Arc Welding",
        "Machine Shop Technology",
        "Electrical Technology",
        "Instrumentation and Control",
    ],
    # Note: provisional — official CG not yet released for this cluster.
    "Maritime Transport": [
        "Navigation",
        "Marine Engineering",
        "Marine Safety and Survival Techniques",
        "Ship Operations and Maintenance",
        "Port Operations",
        "Maritime Law and Regulations",
    ],
}

# ── Legacy ELECTIVE rows that were inserted by the old seed ─────────────────
# Needed by downgrade() to restore the previous state.
_OLD_ACADEMIC_ELECTIVES = [
    "Arts, Social Sciences, and Humanities",
    "Business and Entrepreneurship",
    "Science, Technology, Engineering, and Mathematics (STEM)",
    "Sports, Health, and Wellness",
    "Field Experience",
]
_OLD_TECHPRO_ELECTIVES = [
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


def upgrade() -> None:
    conn = op.get_bind()

    # ── Step 1: delete old ELECTIVE subject rows ─────────────────────────────
    conn.execute(sa.text("DELETE FROM subject WHERE category = 'ELECTIVE'"))

    # ── Step 2: insert clusters ──────────────────────────────────────────────
    cluster_t = sa.table(
        "cluster",
        sa.column("id", sa.Uuid),
        sa.column("name", sa.String),
        sa.column("track", sa.String),
        sa.column("order_index", sa.Integer),
    )
    cluster_name_to_id: dict[str, uuid.UUID] = {}
    cluster_rows: list[dict] = []
    for name, track, order_index in _CLUSTERS:
        cluster_id = uuid.uuid4()
        cluster_name_to_id[name] = cluster_id
        cluster_rows.append(
            {
                "id": cluster_id,
                "name": name,
                "track": track,
                "order_index": order_index,
            }
        )
    op.bulk_insert(cluster_t, cluster_rows)

    # ── Step 3: link each cluster to Grade 11 and Grade 12 ──────────────────
    grade_11_row = conn.execute(
        sa.text("SELECT id FROM grade_level WHERE code = 'GRADE_11'")
    ).fetchone()
    grade_12_row = conn.execute(
        sa.text("SELECT id FROM grade_level WHERE code = 'GRADE_12'")
    ).fetchone()
    if grade_11_row is None or grade_12_row is None:
        raise RuntimeError("GRADE_11 / GRADE_12 not found — run the curriculum seed first")
    grade_11_id = grade_11_row[0]
    grade_12_id = grade_12_row[0]

    cgl_t = sa.table(
        "cluster_grade_level",
        sa.column("cluster_id", sa.Uuid),
        sa.column("grade_level_id", sa.Uuid),
    )
    cgl_rows: list[dict] = []
    for cluster_id in cluster_name_to_id.values():
        cgl_rows.append({"cluster_id": cluster_id, "grade_level_id": grade_11_id})
        cgl_rows.append({"cluster_id": cluster_id, "grade_level_id": grade_12_id})
    op.bulk_insert(cgl_t, cgl_rows)

    # ── Step 4: insert elective subjects ────────────────────────────────────
    subject_t = sa.table(
        "subject",
        sa.column("id", sa.Uuid),
        sa.column("grade_level_id", sa.Uuid),
        sa.column("cluster_id", sa.Uuid),
        sa.column("name", sa.String),
        sa.column("category", sa.String),
        sa.column("order_index", sa.Integer),
    )
    subject_rows: list[dict] = []
    for cluster_name, _, _ in _CLUSTERS:
        cluster_id = cluster_name_to_id[cluster_name]
        subjects = _CLUSTER_SUBJECTS.get(cluster_name, [])
        for order_index, subject_name in enumerate(subjects):
            subject_rows.append(
                {
                    "id": uuid.uuid4(),
                    "grade_level_id": None,
                    "cluster_id": cluster_id,
                    "name": subject_name,
                    "category": "ELECTIVE",
                    "order_index": order_index,
                }
            )
    op.bulk_insert(subject_t, subject_rows)


def downgrade() -> None:
    conn = op.get_bind()

    # Delete all elective subjects (cluster-anchored rows).
    conn.execute(sa.text("DELETE FROM subject WHERE category = 'ELECTIVE'"))
    # Delete cluster_grade_level links.
    conn.execute(sa.text("DELETE FROM cluster_grade_level"))
    # Delete clusters.
    conn.execute(sa.text("DELETE FROM cluster"))

    # Re-insert the old ELECTIVE rows (cluster names as subjects, one set per grade).
    grade_rows = conn.execute(
        sa.text(
            "SELECT id, code FROM grade_level WHERE code IN ('GRADE_11', 'GRADE_12') "
            "ORDER BY code"
        )
    ).fetchall()
    grade_map: dict[str, uuid.UUID] = {row[1]: row[0] for row in grade_rows}

    subject_t = sa.table(
        "subject",
        sa.column("id", sa.Uuid),
        sa.column("grade_level_id", sa.Uuid),
        sa.column("cluster_id", sa.Uuid),
        sa.column("name", sa.String),
        sa.column("category", sa.String),
        sa.column("order_index", sa.Integer),
    )
    old_rows: list[dict] = []
    for _grade_code, grade_id in grade_map.items():
        order = 5  # core subjects occupy 0-4
        for name in _OLD_ACADEMIC_ELECTIVES:
            old_rows.append(
                {
                    "id": uuid.uuid4(),
                    "grade_level_id": grade_id,
                    "cluster_id": None,
                    "name": name,
                    "category": "ELECTIVE",
                    "order_index": order,
                }
            )
            order += 1
        for name in _OLD_TECHPRO_ELECTIVES:
            old_rows.append(
                {
                    "id": uuid.uuid4(),
                    "grade_level_id": grade_id,
                    "cluster_id": None,
                    "name": name,
                    "category": "ELECTIVE",
                    "order_index": order,
                }
            )
            order += 1
    op.bulk_insert(subject_t, old_rows)

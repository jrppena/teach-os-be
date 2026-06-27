"""Lesson-plans PDF export builder.

Produces a DepEd MATATAG / ILAW lesson-plan PDF that mirrors the layout of the
DOCX builder (``docx_export.py``) — the same school header paragraphs, the same
ILAW table structure (1 label column + one column per session), the same section
banners, shading, and ``[Teacher to complete]`` amber highlighting.

Reuses the ``SchoolHeader`` dataclass from ``docx_export`` and the shared
``COLOR_*`` / ``ROW_GUIDANCE`` / ``TEACHER_TODO_PREFIX`` constants from ``constants.py``
so the PDF and DOCX never diverge in content.

Entry point:
    ``build_lesson_plan_pdf(plan, school) -> io.BytesIO``

Pure and synchronous — callers in async contexts must offload via ``run_in_threadpool``.
"""

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.lesson_plans.constants import (
    COLOR_BANNER,
    COLOR_HEADER_BG,
    COLOR_LABEL_BG,
    COLOR_TODO_BG,
    COLOR_WHITE,
    ROW_GUIDANCE,
    TEACHER_TODO_PREFIX,
)
from src.lesson_plans.docx_export import SchoolHeader, _slugify
from src.lesson_plans.schemas import GeneratedLessonPlan

# ── Font / colour constants ───────────────────────────────────────────────────

_FONT = "Times-Roman"
_FONT_BOLD = "Times-Bold"
_FONT_ITALIC = "Times-Italic"
_FONT_BOLD_ITALIC = "Times-BoldItalic"
_SIZE = 10  # base font size (slightly smaller than docx 12pt to fit A4/Letter)
_LEADING = 13  # 1.3× leading gives comfortable readability

# Pre-parsed hex → reportlab Color objects for TableStyle use.
_C_BANNER = colors.HexColor(f"#{COLOR_BANNER}")
_C_HEADER_BG = colors.HexColor(f"#{COLOR_HEADER_BG}")
_C_LABEL_BG = colors.HexColor(f"#{COLOR_LABEL_BG}")
_C_TODO_BG = colors.HexColor(f"#{COLOR_TODO_BG}")
_C_WHITE = colors.HexColor(f"#{COLOR_WHITE}")
_C_BORDER = colors.HexColor("#AAAAAA")
_C_GUIDANCE = colors.HexColor("#555555")

# ── ParagraphStyles ───────────────────────────────────────────────────────────


def _make_styles() -> dict[str, ParagraphStyle]:
    """Build and return a dict of named ParagraphStyles used throughout the builder.

    Inputs: none.
    Outputs: dict mapping style names to ``ParagraphStyle`` instances.
    Side effects: none.
    """
    base = dict(
        fontName=_FONT,
        fontSize=_SIZE,
        leading=_LEADING,
        spaceAfter=0,
        spaceBefore=0,
    )

    def _s(name: str, **overrides: Any) -> ParagraphStyle:
        return ParagraphStyle(name, **{**base, **overrides})

    return {
        "body": _s("body", alignment=4),  # 4 = JUSTIFY
        "body_left": _s("body_left", alignment=0),
        "bold": _s("bold", fontName=_FONT_BOLD, alignment=4),
        "bold_left": _s("bold_left", fontName=_FONT_BOLD, alignment=0),
        "bold_center": _s("bold_center", fontName=_FONT_BOLD, alignment=1),
        "white_bold": _s("white_bold", fontName=_FONT_BOLD, textColor=_C_WHITE, alignment=0),
        "white_bold_center": _s(
            "white_bold_center", fontName=_FONT_BOLD, textColor=_C_WHITE, alignment=1
        ),
        "guidance": _s(
            "guidance",
            fontName=_FONT_ITALIC,
            fontSize=_SIZE - 1,
            leading=_LEADING - 1,
            textColor=_C_GUIDANCE,
            spaceBefore=2,
            alignment=0,
        ),
        "bullet": _s("bullet", alignment=4, leftIndent=10, firstLineIndent=-10),
        "center": _s("center", alignment=1),
        "bold_center_header": _s(
            "bold_center_header",
            fontName=_FONT_BOLD,
            fontSize=_SIZE + 1,
            leading=_LEADING + 1,
            alignment=1,
        ),
    }


# ── Builder state ──────────────────────────────────────────────────────────────


class _Builder:
    """Incremental table builder that accumulates row data and style commands.

    Each call to one of the ``_row_*`` helpers appends to ``self.data`` and
    ``self.cmds``, keeping a cursor (``self.r``) on the current row index so
    that style commands can reference absolute row positions — the same approach
    the DOCX builder uses (each helper knows its row's position).

    Inputs: column count and column widths.
    Outputs: ``(data, cmds)`` ready for ``Table(data, colWidths, style=…)``.
    """

    def __init__(self, col_count: int, col_widths: list[float]) -> None:
        """Initialise builder with column layout and empty row/style accumulators.

        Inputs: total column count (1 + n_sessions), list of column widths in points.
        Side effects: none.
        """
        self.col_count = col_count
        self.col_widths = col_widths
        self.data: list[list[Any]] = []
        self.cmds: list[tuple] = []
        self.r = 0  # current row index

    # ── Primitives ─────────────────────────────────────────────────────────────

    def _push(self, row: list[Any], *cmds: tuple) -> None:
        """Append one row and its associated style commands; advance the cursor.

        Inputs: the row data (list of cell content) and zero or more style tuples.
        Side effects: mutates ``self.data``, ``self.cmds``, ``self.r``.
        """
        self.data.append(row)
        self.cmds.extend(cmds)
        self.r += 1

    def _full_span(self, r: int) -> tuple:
        """Return a SPAN command that merges all columns in row ``r``.

        Inputs: row index.
        Outputs: style tuple.
        Side effects: none.
        """
        return ("SPAN", (0, r), (self.col_count - 1, r))

    def _value_span(self, r: int) -> tuple:
        """Return a SPAN command that merges columns 1..N in row ``r`` (label col excluded).

        Inputs: row index.
        Outputs: style tuple.
        Side effects: none.
        """
        if self.col_count > 2:
            return ("SPAN", (1, r), (self.col_count - 1, r))
        return ("SPAN", (1, r), (1, r))  # no-op but valid for single-session

    # ── Row builders ──────────────────────────────────────────────────────────

    def banner_row(
        self,
        text: str,
        bg: colors.Color,
        style_name: str = "white_bold",
    ) -> None:
        """Add a full-width merged banner row (section headers, title blocks).

        Inputs: banner text, background color, name of the Paragraph style to use.
        Side effects: appends row + style commands; advances cursor.
        """
        r = self.r
        row: list[Any] = [Paragraph(text, _STYLES[style_name])] + [""] * (self.col_count - 1)
        self._push(
            row,
            self._full_span(r),
            ("BACKGROUND", (0, r), (self.col_count - 1, r), bg),
            ("VALIGN", (0, r), (self.col_count - 1, r), "MIDDLE"),
        )

    def info_row(self, label: str, value: str | list[Paragraph]) -> None:
        """Add a lesson-information row: bold label (col 0) + value (cols 1..N merged).

        Inputs: row label text and value (string or list of Paragraphs for bullets).
        Side effects: appends row + style commands; advances cursor.
        """
        r = self.r
        label_cell = _label_cell(label)
        value_cell: Any
        if isinstance(value, list):
            value_cell = value
        else:
            value_cell = Paragraph(value, _STYLES["body_left"])
            if value.lstrip().startswith(TEACHER_TODO_PREFIX):
                self.cmds.append(("BACKGROUND", (1, r), (self.col_count - 1, r), _C_TODO_BG))
        row: list[Any] = [label_cell, value_cell] + [""] * (self.col_count - 2)
        self._push(
            row,
            self._value_span(r),
            ("BACKGROUND", (0, r), (0, r), _C_LABEL_BG),
            ("VALIGN", (0, r), (self.col_count - 1, r), "TOP"),
        )

    def full_width_row(self, label: str, guidance: str, content: Any) -> None:
        """Add a row whose content spans columns 1..N (lesson-wide fields).

        Inputs: row label, italic guidance text, and cell content (Paragraph or list).
        Side effects: appends row + style commands; advances cursor.
        """
        r = self.r
        row: list[Any] = [_label_guidance_cell(label, guidance), content] + [""] * (
            self.col_count - 2
        )
        self._push(
            row,
            self._value_span(r),
            ("BACKGROUND", (0, r), (0, r), _C_LABEL_BG),
            ("VALIGN", (0, r), (self.col_count - 1, r), "TOP"),
        )

    def per_session_row(
        self,
        label: str,
        guidance: str,
        session_cells: list[Any],
        todo_cols: list[int] | None = None,
    ) -> None:
        """Add a per-session row: label+guidance in col 0, one cell per session.

        Inputs: label, guidance, session cell content list (one entry per session),
        and optional list of 0-based session indices whose cells are amber TODO.
        Side effects: appends row + style commands; advances cursor.
        """
        r = self.r
        n = self.col_count - 1
        # Pad / truncate to exactly n session cells.
        cells = list(session_cells[:n])
        while len(cells) < n:
            cells.append(Paragraph("", _STYLES["body_left"]))
        row: list[Any] = [_label_guidance_cell(label, guidance)] + cells
        cmds: list[tuple] = [
            ("BACKGROUND", (0, r), (0, r), _C_LABEL_BG),
            ("VALIGN", (0, r), (self.col_count - 1, r), "TOP"),
        ]
        for col_i in todo_cols or []:
            cmds.append(("BACKGROUND", (col_i + 1, r), (col_i + 1, r), _C_TODO_BG))
        self._push(row, *cmds)

    def session_header_row(self, session_labels: list[str]) -> None:
        """Add the "Lesson Component | Session 1 | …" header row for multi-session plans.

        Inputs: list of session label strings.
        Side effects: appends row + style commands; advances cursor.
        """
        r = self.r
        n = len(session_labels)
        row: list[Any] = [Paragraph("Lesson Component", _STYLES["white_bold"])] + [
            Paragraph(lbl, _STYLES["white_bold"]) for lbl in session_labels
        ]
        cmds = [
            ("BACKGROUND", (0, r), (n, r), _C_BANNER),
            ("VALIGN", (0, r), (n, r), "MIDDLE"),
        ]
        self._push(row, *cmds)

    def build_table(self) -> Table:
        """Build and return the Platypus Table from accumulated data and style commands.

        Inputs: none (uses ``self.data``, ``self.cmds``, ``self.col_widths``).
        Outputs: a configured ``Table`` flowable.
        Side effects: none.
        """
        base_cmds = [
            ("FONT", (0, 0), (-1, -1), _FONT, _SIZE),
            ("LEADING", (0, 0), (-1, -1), _LEADING),
            ("GRID", (0, 0), (-1, -1), 0.5, _C_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        return Table(
            self.data,
            colWidths=self.col_widths,
            style=TableStyle(base_cmds + self.cmds),
            repeatRows=1,
            hAlign="LEFT",
            splitByRow=True,
        )


# ── Cell content helpers ──────────────────────────────────────────────────────


def _label_cell(label: str) -> Paragraph:
    """Return a bold left-aligned Paragraph for a plain label cell (no guidance).

    Inputs: label text.
    Outputs: Paragraph.
    Side effects: none.
    """
    return Paragraph(label, _STYLES["bold_left"])


def _label_guidance_cell(label: str, guidance: str) -> list[Paragraph]:
    """Return a list of Paragraphs: bold label stacked over italic grey guidance.

    Inputs: label text and guidance text.
    Outputs: list of Paragraphs (rendered stacked within the cell).
    Side effects: none.
    """
    items: list[Paragraph] = [Paragraph(label, _STYLES["bold_left"])]
    if guidance:
        items.append(Paragraph(guidance, _STYLES["guidance"]))
    return items


def _bullets(items: list[str]) -> list[Paragraph]:
    """Return a list of bullet Paragraphs (• prefix, justified).

    Inputs: list of string items.
    Outputs: list of Paragraphs.
    Side effects: none.
    """
    return [Paragraph(f"• {item}", _STYLES["bullet"]) for item in items if item]


def _numbered(items: list[str]) -> list[Paragraph]:
    """Return a list of numbered Paragraphs (1. 2. …).

    Inputs: list of string items.
    Outputs: list of Paragraphs.
    Side effects: none.
    """
    return [Paragraph(f"{i + 1}. {item}", _STYLES["body"]) for i, item in enumerate(items)]


def _plain(text: str) -> list[Paragraph]:
    """Split text on newlines and return one justified Paragraph per line.

    Inputs: multiline string.
    Outputs: list of Paragraphs.
    Side effects: none.
    """
    lines = text.split("\n") or [""]
    return [Paragraph(line or " ", _STYLES["body"]) for line in lines]


def _objectives_cell(objectives: list) -> list[Paragraph]:
    """Render a session's learning objectives as Knowledge/Skill/Task triples.

    Inputs: list of ``SessionObjective``-compatible objects.
    Outputs: list of Paragraphs.
    Side effects: none.
    """
    paras: list[Paragraph] = []
    for i, obj in enumerate(objectives):
        if i > 0:
            paras.append(Paragraph(" ", _STYLES["body_left"]))
        paras.append(Paragraph(f"<b>Knowledge:</b> {obj.knowledge}", _STYLES["body"]))
        paras.append(Paragraph(f"<b>Skill:</b> {obj.skill}", _STYLES["body"]))
        paras.append(Paragraph(f"<b>Task:</b> {obj.task}", _STYLES["body"]))
    return paras or [Paragraph(" ", _STYLES["body_left"])]


def _flow_cell(steps: list) -> list[Paragraph]:
    """Render a session's flow steps as numbered bold-title + details Paragraphs.

    Inputs: list of ``FlowStep``-compatible objects with ``title`` and ``details``.
    Outputs: list of Paragraphs.
    Side effects: none.
    """
    paras: list[Paragraph] = []
    for i, step in enumerate(steps):
        text = f"<b>{i + 1}. {step.title}:</b> {step.details}" if step.title else step.details
        paras.append(Paragraph(text, _STYLES["body"]))
    return paras or [Paragraph(" ", _STYLES["body_left"])]


def _todo_indices(texts: list[str]) -> list[int]:
    """Return the 0-based indices of texts that begin with the TODO prefix.

    Inputs: list of per-session text strings.
    Outputs: list of integer indices.
    Side effects: none.
    """
    return [i for i, t in enumerate(texts) if t.lstrip().startswith(TEACHER_TODO_PREFIX)]


# Lazily initialised at module import time (after _make_styles is defined).
_STYLES: dict[str, ParagraphStyle] = _make_styles()


# ── Filename helper ───────────────────────────────────────────────────────────


def pdf_filename(title: str) -> str:
    """Return a safe filename for the PDF export derived from the lesson title.

    Inputs: the lesson title string.
    Outputs: a filename string like ``introduction-to-matrices.pdf``.
    Side effects: none.
    """
    return f"{_slugify(title)}.pdf"


# ── Main builder ──────────────────────────────────────────────────────────────


def build_lesson_plan_pdf(plan: GeneratedLessonPlan, school: SchoolHeader) -> io.BytesIO:
    """Build an in-memory PDF for the given ILAW lesson plan.

    Produces a DepEd MATATAG / ILAW document whose layout mirrors ``docx_export.py``:
    centered school header paragraphs, then a single ILAW Platypus Table with 1 + N
    columns (label column + one per session). Handles 1–5 sessions; for N > 1 a session
    header row labels each column.

    Inputs:
        plan   — the ``GeneratedLessonPlan`` to render (may include local edits).
        school — the teacher's ``SchoolHeader`` for the top header block.
    Outputs:
        A seeked-to-zero ``io.BytesIO`` buffer containing the PDF binary.
    Side effects: none beyond building the in-memory document.
    """
    buf = io.BytesIO()
    margin = 72  # 1 inch in points, matching the DOCX narrow margin

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        topMargin=margin,
        bottomMargin=margin,
        leftMargin=margin,
        rightMargin=margin,
    )

    story: list[Any] = []

    # ── School header (centered paragraphs) ───────────────────────────────────
    header_lines = [
        ("Department of Education", True),
        (school.region or "", False),
        (school.division or "", False),
        (school.district or "", False),
        (school.school_name or "", True),
        (school.school_address or "", False),
    ]
    for text, is_bold in header_lines:
        if not text:
            continue
        style = _STYLES["bold_center"] if is_bold else _STYLES["center"]
        story.append(Paragraph(text, style))

    story.append(Spacer(1, 10))

    # ── Table setup ───────────────────────────────────────────────────────────
    n = len(plan.session_labels)
    col_count = 1 + n

    # Page width = 8.5" - 2 × 1" margins = 6.5"
    label_w = 1.5 * inch
    session_w = (6.5 * inch - label_w) / n
    col_widths = [label_w] + [session_w] * n

    b = _Builder(col_count, col_widths)

    # ── LESSON PLAN title banner ───────────────────────────────────────────────
    b.banner_row("LESSON PLAN", _C_HEADER_BG, "white_bold_center")

    # ── LESSON INFORMATION banner ─────────────────────────────────────────────
    b.banner_row("LESSON INFORMATION", _C_HEADER_BG, "white_bold_center")

    # ── Lesson information rows ───────────────────────────────────────────────
    info = plan.lesson_information
    b.info_row("Lesson Title", info.title)
    b.info_row("Learning Area/s", info.learning_areas)
    b.info_row("Name of Teacher/s", info.teacher_name)
    b.info_row("Grade Level and Section", info.grade_level_and_section)
    b.info_row("No. of Sessions", info.sessions_label)
    b.info_row(
        "References (books, websites, toolkits, etc.)",
        _bullets(info.references) if info.references else [Paragraph("—", _STYLES["body_left"])],
    )
    b.info_row(
        "Declaration of AI Use / See DO 003 s.2026 Annex A & DO 16 s.2026 Sec.2",
        info.ai_declaration,
    )

    # ── Session header row (only for multi-session plans) ─────────────────────
    if n > 1:
        b.session_header_row(plan.session_labels)

    # ── I — INTENTIONS ────────────────────────────────────────────────────────
    b.banner_row(
        "I — INTENTIONS / Meaningful learning experiences are anchored in how well learners "
        "understand what they are learning and why.",
        _C_BANNER,
    )

    b.full_width_row(
        "Learning Competency",
        ROW_GUIDANCE["learning_competency"],
        _numbered(plan.learning_competency),
    )

    b.per_session_row(
        "Learning Objectives",
        ROW_GUIDANCE["learning_objectives"],
        [
            _objectives_cell(
                plan.learning_objectives[i] if i < len(plan.learning_objectives) else []
            )
            for i in range(n)
        ],
    )

    lc_text = plan.learner_context
    b.full_width_row(
        "Learner Context",
        ROW_GUIDANCE["learner_context"],
        _plain(lc_text),
    )
    if lc_text.lstrip().startswith(TEACHER_TODO_PREFIX):
        b.cmds.append(("BACKGROUND", (1, b.r - 1), (col_count - 1, b.r - 1), _C_TODO_BG))

    # ── L — LEARNING EXPERIENCES ──────────────────────────────────────────────
    b.banner_row(
        "L — LEARNING EXPERIENCES / A learning experience is like a thoughtfully prepared meal "
        "— it nourishes, considers the diner's needs, and leaves them satisfied and hungry for more.",
        _C_BANNER,
    )

    pre = [plan.pre_lesson[i] if i < len(plan.pre_lesson) else "" for i in range(n)]
    b.per_session_row(
        "Pre-Lesson",
        ROW_GUIDANCE["pre_lesson"],
        [_plain(t) for t in pre],
        _todo_indices(pre),
    )

    b.per_session_row(
        "Flow / Daloy ng Aralin",
        ROW_GUIDANCE["flow"],
        [_flow_cell(plan.flow[i] if i < len(plan.flow) else []) for i in range(n)],
    )

    b.per_session_row(
        "Learning Resources",
        ROW_GUIDANCE["learning_resources"],
        [
            _bullets(plan.learning_resources[i] if i < len(plan.learning_resources) else [])
            for i in range(n)
        ],
    )

    b.per_session_row(
        "Opportunities for Integration",
        ROW_GUIDANCE["opportunities_for_integration"],
        [
            _bullets(
                plan.opportunities_for_integration[i]
                if i < len(plan.opportunities_for_integration)
                else []
            )
            for i in range(n)
        ],
    )

    # ── A — ASSESSMENT ────────────────────────────────────────────────────────
    b.banner_row(
        "A — ASSESSMENT / Assessments reveal what learners have gained and what they still need to work on.",
        _C_BANNER,
    )

    fa = [
        plan.formative_assessment[i] if i < len(plan.formative_assessment) else "" for i in range(n)
    ]
    b.per_session_row(
        "Formative Assessment",
        ROW_GUIDANCE["formative_assessment"],
        [_plain(t) for t in fa],
        _todo_indices(fa),
    )

    # ── W — WAYS FORWARD ─────────────────────────────────────────────────────
    b.banner_row(
        "W — WAYS FORWARD / Meaningful learning can also happen beyond the classroom.",
        _C_BANNER,
    )

    elo = [
        plan.extended_learning_opportunities[i]
        if i < len(plan.extended_learning_opportunities)
        else ""
        for i in range(n)
    ]
    b.per_session_row(
        "Extended Learning Opportunities",
        ROW_GUIDANCE["extended_learning_opportunities"],
        [_plain(t) for t in elo],
        _todo_indices(elo),
    )

    ref = [plan.reflections[i] if i < len(plan.reflections) else "" for i in range(n)]
    b.per_session_row(
        "Reflections",
        ROW_GUIDANCE["reflections"],
        [_plain(t) for t in ref],
        _todo_indices(ref),
    )

    # ── Signatories ───────────────────────────────────────────────────────────
    b.banner_row("PREPARED, CHECKED AND NOTED BY", _C_HEADER_BG, "white_bold")

    sig = plan.signatories
    b.info_row("Prepared by:", sig.prepared_by)
    b.info_row("Checked by:", sig.checked_by)
    b.info_row("Noted by:", sig.noted_by)

    # ── Assemble document ─────────────────────────────────────────────────────
    story.append(b.build_table())
    doc.build(story)
    buf.seek(0)
    return buf

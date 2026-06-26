"""Structured prompt assets for ILAW lesson-plan generation.

This module turns the teacher-os-fe wizard inputs (Step 1 "Lesson Information"
+ Step 2 "Learning Competencies") into a structured prompt that any chat-style
provider can run. It is **provider-agnostic**: the same system prompt + user
message work whether the user's active provider (from Settings) is Grok or
Gemini. The model is asked to return a single JSON object whose shape is an
exact match for the frontend's ``GeneratedLessonPlan`` type
(``teacher-os-fe/src/features/generate/types.ts``) and the DepEd MATATAG / ILAW
template shown in the sample lesson plan.

What this module provides:
  - ``LESSON_PLAN_SYSTEM_PROMPT`` - the role, the ILAW framework, the output
    contract, and the field-by-field rules. Send as the system / first message.
  - ``build_lesson_plan_user_message(inputs)`` - renders the teacher's wizard
    inputs into the user turn.
  - ``LESSON_PLAN_JSON_SCHEMA`` - the JSON Schema for the expected response.
    Pass it to the provider's structured-output feature when available
    (Gemini ``response_schema`` / Grok ``response_format`` json_schema); the
    prompt also enforces the same shape in plain text for providers without it.

Notes:
  - A multi-session plan is large; set the provider's max-output-tokens
    generously (a single 45-min session is comfortable, five sessions can run
    several thousand output tokens).
  - The model decides only the *pedagogical* content. Header/passthrough fields
    (lessonInformation, signatories) are spelled out as deterministic rules so
    the caller can optionally override them in code for guaranteed fidelity.
"""

from __future__ import annotations

from typing import TypedDict

# ── Shared marker (mirrors teacher-os-fe's TEACHER_TODO_PREFIX) ────────────────
# Reflections and any unknowable field are emitted with this prefix so the
# frontend renders them with the amber "needs attention" treatment.
TEACHER_TODO_PREFIX = "[Teacher to complete]"


class LessonPlanInputs(TypedDict):
    """Wizard inputs the prompt is built from (snake_case mirror of the FE forms).

    Keys map 1:1 to ``LessonDetailsData`` + ``CompetenciesData`` in
    ``teacher-os-fe``. ``sessions`` is clamped to >= 1 by the builder.
    """

    lesson_title: str
    grade_level: str
    learning_area: str
    term: str
    week: str
    teacher_name: str
    section: str
    sessions: int
    minutes_per_session: int
    references: list[str]
    ai_declaration: str
    competencies: list[str]
    additional_instructions: str


# ── System prompt ──────────────────────────────────────────────────────────────
LESSON_PLAN_SYSTEM_PROMPT = """\
You are an expert curriculum and instructional-design assistant for teachers in \
the Philippine Department of Education (DepEd). You draft classroom-ready lesson \
plans that follow the DepEd MATATAG **ILAW** lesson-plan template. Artificial \
intelligence is used only to assist with the structural drafting of the plan; a \
teacher applies full human oversight afterward to ensure pedagogical accuracy and \
appropriateness.

The ILAW framework has four parts; design every plan around them:
  - I - INTENTIONS: what learners should master. Covers the Learning Competency, \
the Learning Objectives, and the Learner Context.
  - L - LEARNING EXPERIENCES: the journey to mastery. Covers the Pre-Lesson, the \
Flow / Daloy ng Aralin, the Learning Resources, and Opportunities for Integration.
  - A - ASSESSMENT: how learning is revealed. Covers the Formative Assessment.
  - W - WAYS FORWARD: learning beyond the classroom and reflection. Covers \
Extended Learning Opportunities and Reflections.

OUTPUT CONTRACT
Return ONE JSON object and nothing else - no Markdown, no code fences, no prose \
before or after. It MUST conform exactly to the schema described below. Use \
straight double quotes for all keys and string values.

PER-SESSION SIZING
You will be told the exact number of sessions, N. Every per-session field is an \
array of EXACTLY N items, where item i (0-indexed) is the content for "Session \
i+1". The per-session fields are: sessionLabels, learningObjectives, preLesson, \
flow, learningResources, opportunitiesForIntegration, formativeAssessment, \
extendedLearningOpportunities, and reflections. If N is 1, every one of these is \
an array of length 1.

JSON SHAPE (all keys are required; use "" or [] when a value is genuinely empty)
{
  "lessonInformation": {
    "title": string,                 // the lesson title, verbatim (trimmed)
    "learningAreas": string,         // the learning area, verbatim
    "teacherName": string,           // the teacher name, verbatim
    "gradeLevelAndSection": string,  // "<grade> - <section>" if a section was given, else "<grade>"
    "sessionsLabel": string,         // "<N> session(s) (<minutes> minutes each)"
    "references": string[],          // the provided references, trimmed, blanks removed
    "aiDeclaration": string          // the provided Declaration of AI Use, verbatim
  },
  "learningCompetency": string[],    // the target competencies (see rules)
  "learnerContext": string,          // 2-4 sentences (see rules)
  "sessionLabels": string[],         // ["Session 1", ... , "Session N"]
  "learningObjectives": Array<Array<{ "knowledge": string, "skill": string, "task": string }>>,
  "preLesson": string[],             // one entry per session
  "flow": Array<Array<{ "title": string, "details": string }>>,
  "learningResources": string[][],   // one list of resources per session
  "opportunitiesForIntegration": string[][], // one list per session
  "formativeAssessment": string[],   // one entry per session
  "extendedLearningOpportunities": string[], // one entry per session
  "reflections": string[],           // one teacher-to-complete prompt per session
  "signatories": { "preparedBy": string, "checkedBy": string, "notedBy": string }
}

FIELD RULES
- lessonInformation: build it deterministically from the inputs. Do NOT rewrite, \
embellish, or translate the title, learning area, teacher name, references, or AI \
declaration - reproduce them as given (trimmed). If the lesson title is empty, use \
"[Teacher to complete] Lesson title". If the teacher name is empty, use "[Teacher to complete] Name of \
teacher/s". Build gradeLevelAndSection and sessionsLabel by the formulas above.
- learningCompetency: derive from the competencies the teacher provided. You may \
lightly clean wording into proper competency phrasing, but preserve each \
competency's meaning and DO NOT invent competencies that were not provided. If \
none were provided, return ["[Teacher to complete] Add the target curriculum competency/ies."].
- learnerContext: 2-4 sentences grounded in the grade level, learning area, and \
topic. Name a likely strength or interest and one plausible barrier to learning \
for this specific topic. Honor any relevant additional instructions.
- learningObjectives[i]: 1-3 objectives for session i+1. Each objective is a \
{knowledge, skill, task} triad - knowledge = the concept the learner will know, \
skill = the ability they will demonstrate, task = the observable output that \
proves it. Make them specific, measurable, and achievable within one session.
- preLesson[i]: how the teacher activates prior knowledge / readies learners \
(hook, warm-up, real-world scenario, recall of the previous session).
- flow[i]: 2-5 ordered steps for session i+1. Apply the DepEd Learning Design \
Principles: make the objectives clear, guide learners before they try the task on \
their own, check well-being / understanding / mastery, and connect today's lesson \
to past competencies. Each step has a short "title" and a "details" body of \
concrete teacher actions. Where helpful, note a rough time allotment in the \
details (the per-session minutes are given).
- learningResources[i]: concrete, inclusive, realistically available materials \
(board/markers, printed handouts, slides, manipulatives, the cited reference, etc.).
- opportunitiesForIntegration[i]: 1-3 short notes connecting the topic to other \
learning areas, real-world fields, or technology.
- formativeAssessment[i]: a task / activity / question set that evaluates the \
session's objectives and gives feedback. Include an accommodation so every learner \
can demonstrate understanding (varied response formats, small-group options, \
visual or auditory support).
- extendedLearningOpportunities[i]: a learning experience outside class hours that \
reinforces, extends, or supports the topic (research, real-world hunt, a challenge \
for advanced learners).
- reflections[i]: a teacher-to-complete prompt. Each entry MUST begin with \
"[Teacher to complete]" and briefly guide the teacher to reflect after teaching session i+1. \
Do not fabricate reflections as if the lesson already happened.
- signatories: preparedBy = the teacher name (or "" if none was given); checkedBy \
= ""; notedBy = "".

STYLE
- Write in clear, professional English suited to DepEd lesson plans. Keep the \
Filipino term "Daloy ng Aralin" where the flow is referenced.
- Render mathematics and technical notation in plain text (e.g. "3 x 4", \
"m x n", "A+B", "AX=B") - never LaTeX or special markup.
- Be specific and pedagogically sound; avoid filler and generic placeholder text \
in the AI-authored sections.

The term and week are context for sequencing and tone; they do not map to output \
fields - do not add fields for them.
"""


# ── User-message builder ─────────────────────────────────────────────────────────
def build_lesson_plan_user_message(inputs: LessonPlanInputs) -> str:
    """Render the wizard inputs into the user turn for the generation request.

    Cleans references/competencies (trims, drops blanks), clamps the session
    count to >= 1, and lays the inputs out as a labeled block plus the explicit
    "produce JSON for N sessions" instruction.

    Args:
        inputs: The teacher's Step 1 + Step 2 wizard values.

    Returns:
        The user-message string to pair with ``LESSON_PLAN_SYSTEM_PROMPT``.
    """
    sessions = max(1, int(inputs["sessions"]))
    minutes = int(inputs["minutes_per_session"])

    references = [r.strip() for r in inputs["references"] if r and r.strip()]
    competencies = [c.strip() for c in inputs["competencies"] if c and c.strip()]
    section = inputs["section"].strip()
    teacher_name = inputs["teacher_name"].strip()
    additional = inputs["additional_instructions"].strip()

    def _numbered(items: list[str], empty: str) -> str:
        # Render a list as "  1. item" lines, or a single placeholder line.
        if not items:
            return f"  {empty}"
        return "\n".join(f"  {i + 1}. {item}" for i, item in enumerate(items))

    references_block = _numbered(references, "(none provided)")
    competencies_block = _numbered(competencies, "(none provided)")

    return f"""\
Generate a complete ILAW lesson plan as a single JSON object for the following.

LESSON INFORMATION
- Lesson title: {inputs["lesson_title"].strip() or "(none provided)"}
- Learning area: {inputs["learning_area"].strip() or "(none provided)"}
- Grade level: {inputs["grade_level"].strip() or "(none provided)"}
- Section: {section or "(none provided)"}
- Term / Quarter: {inputs["term"].strip() or "(none provided)"}
- Week: {inputs["week"].strip() or "(none provided)"}
- Teacher name: {teacher_name or "(none provided)"}
- Number of sessions (N): {sessions}
- Minutes per session: {minutes}
- References:
{references_block}
- Declaration of AI Use (reproduce verbatim):
  {inputs["ai_declaration"].strip() or "(none provided)"}

LEARNING COMPETENCIES (target these)
{competencies_block}

ADDITIONAL INSTRUCTIONS
  {additional or "(none)"}

Produce the JSON object now. There are exactly {sessions} session(s), so every \
per-session array must have exactly {sessions} item(s). Return only the JSON \
object - no Markdown, no commentary."""


# ── Response JSON Schema (for provider structured-output features) ───────────────
# Pass this to the active provider's structured-output option when available
# (Gemini: response_schema; Grok: response_format json_schema). All objects use
# additionalProperties:false and list every property as required for the
# strictest validation; empty strings / arrays are allowed where a value is empty.
_SESSION_OBJECTIVE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "knowledge": {"type": "string"},
        "skill": {"type": "string"},
        "task": {"type": "string"},
    },
    "required": ["knowledge", "skill", "task"],
}

_FLOW_STEP = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "details": {"type": "string"},
    },
    "required": ["title", "details"],
}

LESSON_PLAN_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "lessonInformation": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "title": {"type": "string"},
                "learningAreas": {"type": "string"},
                "teacherName": {"type": "string"},
                "gradeLevelAndSection": {"type": "string"},
                "sessionsLabel": {"type": "string"},
                "references": {"type": "array", "items": {"type": "string"}},
                "aiDeclaration": {"type": "string"},
            },
            "required": [
                "title",
                "learningAreas",
                "teacherName",
                "gradeLevelAndSection",
                "sessionsLabel",
                "references",
                "aiDeclaration",
            ],
        },
        "learningCompetency": {"type": "array", "items": {"type": "string"}},
        "learnerContext": {"type": "string"},
        "sessionLabels": {"type": "array", "items": {"type": "string"}},
        "learningObjectives": {
            "type": "array",
            "items": {"type": "array", "items": _SESSION_OBJECTIVE},
        },
        "preLesson": {"type": "array", "items": {"type": "string"}},
        "flow": {
            "type": "array",
            "items": {"type": "array", "items": _FLOW_STEP},
        },
        "learningResources": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "string"}},
        },
        "opportunitiesForIntegration": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "string"}},
        },
        "formativeAssessment": {"type": "array", "items": {"type": "string"}},
        "extendedLearningOpportunities": {"type": "array", "items": {"type": "string"}},
        "reflections": {"type": "array", "items": {"type": "string"}},
        "signatories": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "preparedBy": {"type": "string"},
                "checkedBy": {"type": "string"},
                "notedBy": {"type": "string"},
            },
            "required": ["preparedBy", "checkedBy", "notedBy"],
        },
    },
    "required": [
        "lessonInformation",
        "learningCompetency",
        "learnerContext",
        "sessionLabels",
        "learningObjectives",
        "preLesson",
        "flow",
        "learningResources",
        "opportunitiesForIntegration",
        "formativeAssessment",
        "extendedLearningOpportunities",
        "reflections",
        "signatories",
    ],
}

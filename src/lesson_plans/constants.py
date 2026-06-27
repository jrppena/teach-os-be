"""Lesson-plans domain constants.

ILAW label/guidance strings for the DOCX export builder. These mirror the FE
``ROW_GUIDANCE`` map (teacher-os-fe/src/features/generate/types.ts) so that the
exported document matches the on-screen rendering.
"""

# Italic guidance copy shown beneath each row label in the ILAW table,
# taken verbatim from the official DepEd MATATAG template.
ROW_GUIDANCE: dict[str, str] = {
    "learning_competency": (
        "Write the competency/ies from the curriculum that we are targeting, and the content "
        "or performance standards applicable to the sessions."
    ),
    "learning_objectives": (
        "Write the smaller knowledge, skills, or tasks from the competency that the learners "
        "will work on and be able to show by the end of the sessions. 3 objectives only."
    ),
    "learner_context": (
        "Write your observations of your learners, and how they have been performing or "
        "responding to learning experiences recently. Include strengths, interests, and "
        "possible barriers to learning."
    ),
    "pre_lesson": "Describe how you will help the learners get ready for the lesson.",
    "flow": (
        "Describe the activities that you can implement in 1 or more sessions to meet the "
        "learning objectives. Apply the Learning Design Principles by thinking about how to "
        "make the objectives clear, guide learners before they try the task, check well-being "
        "and mastery, and connect today's lesson to past competencies."
    ),
    "learning_resources": (
        "List down the learning resources that will help you reach your objectives. Ensure "
        "that they are available and inclusive."
    ),
    "opportunities_for_integration": (
        "Write down any possibilities to meaningfully connect with other learning areas, "
        "special topics, or technology."
    ),
    "formative_assessment": (
        "Create a task, activity, or questions to evaluate learning and provide feedback. "
        "Provide appropriate accommodations so all learners can demonstrate their understanding."
    ),
    "extended_learning_opportunities": (
        "Suggest other learning experiences outside class hours that learners may access to "
        "reinforce what they have learned or spark their curiosity."
    ),
    "reflections": (
        "Think about what you need to change for the next session based on what happened "
        "today. Note what learners are interested in exploring and what you'd like your "
        "instructional coach to help you with."
    ),
}

# Hex colours used in the DOCX table (without the leading #).
COLOR_BANNER = "2E4057"  # dark blue — ILAW section bands (I/L/A/W)
COLOR_LABEL_BG = "E8EDF2"  # light steel — left label column background
COLOR_HEADER_BG = "2E4057"  # same dark blue for the LESSON PLAN / info banners
COLOR_TODO_BG = "FFF3CD"  # amber — [Teacher to complete] cells
COLOR_WHITE = "FFFFFF"

TEACHER_TODO_PREFIX = "[Teacher to complete]"

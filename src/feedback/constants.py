"""Feedback domain constants.

Enumerates the feedback categories a teacher can pick on the FE ``/feedback``
form. Kept as a ``StrEnum`` so the value is both the wire format and the stored
column value.
"""

from enum import StrEnum


class FeedbackCategory(StrEnum):
    """Category a teacher assigns to a feedback submission.

    Mirrors the FE ``FeedbackCategory`` union. ``GENERAL`` is the default when
    the client omits a category.
    """

    GENERAL = "GENERAL"
    BUG = "BUG"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    LESSON_PLAN_QUALITY = "LESSON_PLAN_QUALITY"

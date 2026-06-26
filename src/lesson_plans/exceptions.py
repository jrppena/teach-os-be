"""Lesson-plans domain exceptions.

Thin ``AppException`` subclasses (see ``src/exceptions.py``) carrying the right
HTTP status + a client-safe ``detail`` message. The global ``app_exception_handler``
serializes them to ``{"detail": ...}``.
"""

from src.exceptions import AppException


class NoProviderKeyConfigured(AppException):
    """No API key is stored for the user's active AI provider.

    Maps to 409 — the FE should route the user to Settings to add a key. The
    provider name is interpolated so the message is actionable.
    """

    def __init__(self, provider: str) -> None:
        super().__init__(
            status_code=409,
            detail=(
                f"No API key configured for your active provider ({provider}). "
                "Add one in Settings, then try again."
            ),
        )


class ProviderError(AppException):
    """The provider call failed (HTTP error, timeout, or transport failure).

    Maps to 502 — the upstream AI provider, not our API, is at fault.
    """

    def __init__(self, detail: str = "The AI provider request failed. Please try again.") -> None:
        super().__init__(status_code=502, detail=detail)


class ProviderResponseError(AppException):
    """The provider responded but the payload was missing, unparseable, or off-schema.

    Maps to 502 — we received a response we could not turn into a valid plan.
    """

    def __init__(
        self,
        detail: str = "The AI provider returned an unexpected response. Please try again.",
    ) -> None:
        super().__init__(status_code=502, detail=detail)

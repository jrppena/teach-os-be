"""Lesson-plans domain configuration.

Per-domain ``BaseSettings`` (one-BaseSettings-per-domain, per AGENTS.md) for the
AI generation call: which model each provider uses, the provider base URLs, the
output-token ceiling, and the HTTP timeout. Every field has a default, so no
``.env`` changes are required to run; override any of them with a ``LESSON_PLAN_``
prefixed env var.

Model-ID notes:
- ``GEMINI_MODEL`` defaults to ``gemini-2.5-flash`` — available on the Gemini free
  tier and the default active provider.
- ``GROK_MODEL`` defaults to ``grok-3``. xAI has no true free tier; override this
  with whatever model the account's credits support via ``LESSON_PLAN_GROK_MODEL``.
- The legacy ``AI_*`` vars in ``.env`` are Anthropic leftovers and are unused here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class LessonPlanConfig(BaseSettings):
    """Generation settings for the lesson-plans domain.

    Inputs: optional ``LESSON_PLAN_*`` env vars (all have defaults).
    Outputs: typed config consumed by ``lesson_plans.providers``.
    Side effects: none.
    """

    model_config = SettingsConfigDict(
        env_prefix="LESSON_PLAN_",
        env_file=".env",
        extra="ignore",
    )

    # Per-provider model IDs (env-overridable; confirmed against provider docs).
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GROK_MODEL: str = "grok-3"

    # Provider REST base URLs.
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    GROK_BASE_URL: str = "https://api.x.ai/v1"

    # Output-token ceiling for a full multi-session plan, and request timeout.
    MAX_OUTPUT_TOKENS: int = 8192
    TIMEOUT_SECONDS: float = 90.0


settings = LessonPlanConfig()

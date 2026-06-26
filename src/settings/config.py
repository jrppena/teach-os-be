"""Settings domain configuration.

Per-domain ``BaseSettings`` for the provider-key encryption secret, following the
one-``BaseSettings``-per-domain pattern in AGENTS.md.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsConfig(BaseSettings):
    """Reads the Fernet encryption key from the environment.

    Inputs: ``PROVIDER_KEY_ENCRYPTION_KEY`` env var — a URL-safe base64-encoded
    32-byte Fernet key.  Generate one with::

        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    Outputs: typed config consumed by ``src/settings/utils.py``.
    Side effects: raises a validation error at startup if the var is absent.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    PROVIDER_KEY_ENCRYPTION_KEY: str


settings = SettingsConfig()

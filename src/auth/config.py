# Firebase auth configuration loaded from individual FIREBASE_* env vars.
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthConfig(BaseSettings):
    """Maps FIREBASE_* env vars to the fields expected by a service-account cert dict."""

    model_config = SettingsConfigDict(
        env_prefix="FIREBASE_",
        env_file=".env",
        extra="ignore",
    )

    TYPE: str = "service_account"
    PROJECT_ID: str
    PRIVATE_KEY_ID: str
    PRIVATE_KEY: str
    CLIENT_EMAIL: str
    CLIENT_ID: str
    AUTH_URI: str = "https://accounts.google.com/o/oauth2/auth"
    TOKEN_URI: str = "https://oauth2.googleapis.com/token"
    AUTH_PROVIDER_X509_CERT_URL: str = "https://www.googleapis.com/oauth2/v1/certs"
    CLIENT_X509_CERT_URL: str
    UNIVERSE_DOMAIN: str = "googleapis.com"


auth_settings = AuthConfig()
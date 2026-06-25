# Firebase app initialisation — builds cert dict from individual env vars.
import firebase_admin
from firebase_admin import credentials

from src.auth.config import auth_settings


def init_firebase() -> None:
    """Call once at app startup (inside lifespan).

    Constructs the service-account cert dict from FIREBASE_* env vars so no
    JSON file is needed on disk.
    """
    if firebase_admin._apps:
        return  # already initialised (e.g. during tests)

    cert_dict = {
        "type": auth_settings.TYPE,
        "project_id": auth_settings.PROJECT_ID,
        "private_key_id": auth_settings.PRIVATE_KEY_ID,
        # Newlines are escaped in .env; restore them for the RSA key.
        "private_key": auth_settings.PRIVATE_KEY.replace("\\n", "\n"),
        "client_email": auth_settings.CLIENT_EMAIL,
        "client_id": auth_settings.CLIENT_ID,
        "auth_uri": auth_settings.AUTH_URI,
        "token_uri": auth_settings.TOKEN_URI,
        "auth_provider_x509_cert_url": auth_settings.AUTH_PROVIDER_X509_CERT_URL,
        "client_x509_cert_url": auth_settings.CLIENT_X509_CERT_URL,
        "universe_domain": auth_settings.UNIVERSE_DOMAIN,
    }
    cred = credentials.Certificate(cert_dict)
    firebase_admin.initialize_app(cred)
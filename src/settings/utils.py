"""Settings domain encryption/masking utilities.

Module-level Fernet instance (thread-safe) backed by ``PROVIDER_KEY_ENCRYPTION_KEY``.
Provides ``encrypt``/``decrypt`` for keys at rest and ``mask`` for the write-only
GET response — decrypts server-side, then masks, so we avoid a denormalized ``last4``
column.
"""

from cryptography.fernet import Fernet

from src.settings.config import settings

_fernet = Fernet(settings.PROVIDER_KEY_ENCRYPTION_KEY)

_MASK_CHAR = "•"
_PREVIEW_CHARS = 4


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext API key using Fernet (AES-128-CBC + HMAC-SHA256).

    Inputs: the raw key string from the user.
    Outputs: URL-safe base64-encoded Fernet token (str).
    Side effects: none.
    """
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a stored Fernet token back to the original plaintext.

    Inputs: the ciphertext string as stored in the DB.
    Outputs: the original plaintext key.
    Side effects: none (raises ``InvalidToken`` if the ciphertext is corrupt).
    """
    return _fernet.decrypt(ciphertext.encode()).decode()


def mask(plaintext: str) -> str:
    """Produce a masked preview of a plaintext key (e.g. ``"••••1a2b"``).

    Shows the last ``_PREVIEW_CHARS`` characters preceded by bullets.  When the
    key is ``_PREVIEW_CHARS`` characters or shorter, returns all bullets so no
    meaningful portion is exposed.

    Inputs: the raw plaintext key.
    Outputs: a masked string safe to return in a GET response.
    Side effects: none.
    """
    if len(plaintext) <= _PREVIEW_CHARS:
        return _MASK_CHAR * len(plaintext)
    suffix = plaintext[-_PREVIEW_CHARS:]
    return _MASK_CHAR * _PREVIEW_CHARS + suffix

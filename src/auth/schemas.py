"""Auth domain schemas.

Holds the decoded-token model returned by the Firebase auth dependency. The
canonical user profile lives in the ``users`` domain (``src/users/schemas.py``);
this module only describes the identity carried by a verified Firebase ID token.
"""

from pydantic import BaseModel


class FirebaseUser(BaseModel):
    """Decoded Firebase ID token payload attached to a request.

    Returned by ``get_current_user`` (see ``src/auth/dependencies.py``) after the
    Bearer token is verified by ``firebase_admin``. This is *not* the DB user — it
    is the identity claims Firebase vouches for.

    Inputs: built from the dict returned by ``firebase_auth.verify_id_token``.
    Outputs: a typed object exposing ``uid``/``email``/``name``/``email_verified``.
    Side effects: none.
    """

    uid: str
    email: str | None = None
    name: str | None = None
    email_verified: bool = False

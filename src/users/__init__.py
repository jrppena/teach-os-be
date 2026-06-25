"""Users domain package.

The canonical user profile that backs Firebase auth: a local PostgreSQL row keyed
by ``firebase_uid``. Exposes the ORM model, request/response schemas, and the
service functions consumed by ``src/auth/router.py``.
"""

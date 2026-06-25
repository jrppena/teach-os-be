# Teacher OS — Backend

FastAPI backend for the Lesson Plan Generator. Authenticates teachers via Firebase and serves lesson plan generation through the Anthropic Claude API.

---

## Tech Stack

| Layer | Library |
|---|---|
| Framework | FastAPI 0.115+, Uvicorn (ASGI) |
| Auth | Firebase Admin SDK, PyJWT |
| Database | PostgreSQL (Neon), SQLAlchemy 2.0 async, asyncpg, Alembic |
| AI | Anthropic Claude API |
| Config | Pydantic Settings v2, python-dotenv |
| Tooling | Ruff (lint + format), pytest + pytest-asyncio |

---

## Prerequisites

- Python 3.11+
- A reachable PostgreSQL database (project uses [Neon](https://neon.tech))
- A Firebase project with a service account
- An Anthropic API key

---

## Local Setup

### 1. Create and activate a virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2. Install the package and all dependencies

```bash
pip install -e .
```

To also install dev tools (ruff, pytest):

```bash
pip install -e ".[dev]"
```

### 3. Configure environment variables

Copy the template and fill in your values:

```bash
cp .env.example .env   # or create .env manually — see the section below
```

**Required `.env` keys:**

```dotenv
# Database
DATABASE_URL=postgresql+asyncpg://user:password@host/dbname?sslmode=require

# Firebase (individual vars — no JSON file needed)
FIREBASE_TYPE=service_account
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY_ID=...
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxx@your-project.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=...
FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token
FIREBASE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
FIREBASE_CLIENT_X509_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/...
FIREBASE_UNIVERSE_DOMAIN=googleapis.com

# Anthropic
AI_API_KEY=sk-ant-...
AI_MODEL=claude-sonnet-4-6
AI_MAX_TOKENS=2048

# App
APP_ENVIRONMENT=local          # local | staging | production
APP_CORS_ORIGINS=http://localhost:3000
APP_SECRET_KEY=change-me-in-production
```

> **Note:** `DATABASE_URL` must use the `postgresql+asyncpg://` scheme for async support.

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the development server

```bash
uvicorn src.main:app --reload
```

The API will be available at `http://localhost:8000`.  
Interactive docs (Swagger UI) are at `http://localhost:8000/docs` — visible only when `APP_ENVIRONMENT` is `local` or `staging`.

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Health check |
| `POST` | `/api/v1/auth/register` | Firebase token | Register a new user after sign-up |
| `GET` | `/api/v1/auth/user/{uid}` | Firebase token | Fetch the authenticated user's profile |

All protected routes require a `Authorization: Bearer <firebase-id-token>` header.

---

## Project Structure

```
src/
├── main.py           # App factory, lifespan, middleware, router registration
├── config.py         # Global app settings (APP_* prefix)
├── database.py       # Async engine, session factory, Base, get_db()
├── exceptions.py     # AppException + handler
├── auth/
│   ├── config.py     # Firebase settings (FIREBASE_* prefix)
│   ├── firebase.py   # Initialises Firebase Admin SDK at startup
│   ├── dependencies.py  # get_current_user, CurrentUser type alias
│   ├── router.py     # /auth/register, /auth/user/{uid}
│   └── schemas.py    # RegisterInput, FirebaseUser
└── users/
    ├── models.py     # User SQLAlchemy model
    ├── schemas.py    # UserResponse (camelCase aliases for FE)
    └── service.py    # get_by_firebase_uid, create_user, touch_last_login
migrations/
└── versions/
    └── 2026-06-25_create_user_table.py
```

---

## Common Commands

```bash
# Lint and auto-fix
ruff check --fix src

# Format
ruff format src

# Run tests
pytest

# Run tests with coverage
pytest --cov=src

# Create a new migration after model changes
alembic revision --autogenerate -m "describe_change"

# Apply migrations
alembic upgrade head

# Downgrade one step
alembic downgrade -1
```

---

## Environment Notes

- **Docs UI** (`/docs`, `/redoc`) are disabled in production (`APP_ENVIRONMENT=production`).
- **CORS** origins are set via `APP_CORS_ORIGINS` as a comma-separated string (e.g. `http://localhost:3000,https://yourapp.com`).
- The `src/lesson_plans/` domain is not yet implemented — its router import is commented out in `src/main.py`.

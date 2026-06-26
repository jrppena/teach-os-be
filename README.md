# Teacher OS — Lesson Plan Generator (Backend)

The API that turns a few classroom details into a complete, DepEd-aligned lesson plan.

---

## Introduction

Filipino teachers spend hours every week writing lesson plans by hand, following the
DepEd **MATATAG / ILAW** format. **Teacher OS** exists to give that time back.

This repository is the **backend** — the engine behind the app. A teacher signs in,
fills out a short wizard (lesson title, grade level, subject, how many sessions, and
the competencies they want to cover), and the backend does the rest: it builds a
carefully structured prompt, sends it to the teacher's own AI provider, validates the
result, locks in the official header and footer details, and saves the finished plan so
it can be opened again later.

A few ideas keep the whole thing simple and safe:

- **Bring your own AI key.** Each teacher stores their own Gemini or Grok API key. Keys
  are encrypted before they ever touch the database and are never sent back to the
  browser.
- **Sign in with Firebase.** Identity is handled by Firebase, so the backend never
  stores passwords.
- **The format is guaranteed.** The AI fills in the teaching content, but the backend
  always overrides the official fields (header, signatories, session labels) so every
  plan comes out in the correct DepEd structure.

> **Heads up:** This is a backend service (a REST API). It is meant to be run together
> with the Teacher OS frontend, which provides the screens teachers actually click on.

---

## Technology Stack

| Layer | What we use |
|---|---|
| Language | Python 3.11+ |
| Web framework | FastAPI + Uvicorn (ASGI server) |
| Data validation / config | Pydantic v2 + pydantic-settings |
| Database | PostgreSQL (works great with [Neon](https://neon.tech)) |
| Database access | SQLAlchemy 2.0 (async) + asyncpg |
| Migrations | Alembic |
| Authentication | Firebase Admin SDK (+ PyJWT) |
| AI generation | Google **Gemini** or xAI **Grok**, called directly over `httpx` |
| Encryption | `cryptography` (Fernet) for storing provider keys at rest |
| Tooling | Ruff (lint + format), pytest + pytest-asyncio |

---

## Quick Start

This guide takes you from a fresh clone to your **first generated lesson plan**.

### What you'll need first

- **Python 3.11 or newer**
- A **PostgreSQL** database you can reach (a free [Neon](https://neon.tech) project works well)
- A **Firebase** project with a service account (for sign-in)
- An **AI provider key** — either a Google **Gemini** or an xAI **Grok** API key

### 1. Set up your environment

```bash
# Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install the app (add ".[dev]" for the linter and tests)
pip install -e ".[dev]"
```

### 2. Create your `.env` file

Create a file named `.env` in the project root and fill in your own values:

```dotenv
# --- Database (must use the async driver scheme) ---
DATABASE_URL=postgresql+asyncpg://user:password@host/dbname?sslmode=require

# --- App ---
APP_ENVIRONMENT=local                       # local | staging | production
APP_CORS_ORIGINS=http://localhost:3000      # comma-separated list of allowed origins
APP_SECRET_KEY=change-me

# --- Provider-key encryption (generate the value with the command below) ---
PROVIDER_KEY_ENCRYPTION_KEY=your-fernet-key

# --- Firebase service account (individual fields — no JSON file needed) ---
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY_ID=...
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxx@your-project.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=...
FIREBASE_CLIENT_X509_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/...
```

Generate the encryption key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> **Note:** `DATABASE_URL` must start with `postgresql+asyncpg://` so the app can talk to
> the database asynchronously. The teacher's Gemini/Grok keys are **not** set here — they
> are added per-user through the API after sign-in (see step 5).

### 3. Set up the database

```bash
alembic upgrade head
```

This creates the `user`, `provider_setting`, `provider_key`, and `lesson_plan` tables.

### 4. Start the server

```bash
uvicorn src.main:app --reload
```

The API is now live at **http://localhost:8000**.
When `APP_ENVIRONMENT` is `local` or `staging`, you can explore and try every endpoint
in your browser at **http://localhost:8000/docs**.

### 5. Your first successful action

Every protected request needs a Firebase ID token sent as a header:
`Authorization: Bearer <firebase-id-token>`. The frontend obtains this token when a
teacher logs in. The typical first run looks like this:

1. **Register the teacher** — `POST /api/v1/auth/register` creates their profile row.
2. **Save an AI key** — `PATCH /api/v1/settings/provider-keys` to store a Gemini or Grok
   key and choose the active provider. The key is encrypted before it's saved.
3. **Generate a plan** — `POST /api/v1/lesson-plans` with the wizard details:

   ```json
   {
     "lessonTitle": "Introduction to Photosynthesis",
     "gradeLevel": "Grade 7",
     "learningArea": "Science",
     "sessions": 2,
     "minutesPerSession": 45,
     "competencies": ["Explain how plants make their own food"]
   }
   ```

   You'll get back a fully structured ILAW lesson plan, already saved to your history. 🎉

---

## API Reference (at a glance)

All protected routes require an `Authorization: Bearer <firebase-id-token>` header.

| Method | Path | What it does |
|---|---|---|
| `GET` | `/health` | Public health check |
| `POST` | `/api/v1/auth/register` | Create a teacher's profile after sign-up |
| `GET` | `/api/v1/auth/user/{uid}` | Fetch the signed-in teacher's profile |
| `GET` | `/api/v1/settings/provider-keys` | See which AI keys are configured (masked) |
| `PATCH` | `/api/v1/settings/provider-keys` | Add/clear a key or switch the active provider |
| `POST` | `/api/v1/lesson-plans` | Generate and save a new lesson plan |
| `GET` | `/api/v1/lesson-plans` | List the teacher's saved plans |
| `GET` | `/api/v1/lesson-plans/{id}` | Open one saved plan in full |
| `DELETE` | `/api/v1/lesson-plans/{id}` | Delete a saved plan |

---

## Project Structure

```
src/
├── main.py             # App setup: middleware, startup, route registration
├── config.py           # Global app settings (APP_* env vars)
├── database.py         # Async engine, session factory, Base model
├── exceptions.py       # Shared error type + handler
├── auth/               # Firebase token verification + register/profile routes
├── users/              # Canonical teacher profile (the DB user)
├── settings/           # Encrypted, per-user AI provider keys
└── lesson_plans/       # Plan generation (Gemini/Grok over httpx) + history
migrations/             # Alembic database migrations
```

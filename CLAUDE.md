<project-context>

**Project:** `teacher-os-be` — the backend for a Lesson Plan Generator (package name
`lesson-plan-generator-api`). A FastAPI service that authenticates teachers via Firebase
and generates lesson plans using the Anthropic Claude API.

**Tech stack** (pinned in [pyproject.toml](pyproject.toml)):
- Python 3.11+, FastAPI ≥0.115, Uvicorn (ASGI server)
- Pydantic v2 (≥2.7) + pydantic-settings ≥2.4 for typed config
- SQLAlchemy 2.0 **async** + asyncpg (PostgreSQL), Alembic ≥1.13 for migrations
- `firebase-admin` for ID-token auth, `anthropic` SDK for AI generation, `httpx` for HTTP
- Tooling: `ruff` (lint + format), `pytest` + `pytest-asyncio` (auto mode) + `pytest-cov`

**Architecture (big picture):**
- Domain-driven layout under `src/`. Each bounded context is a package with its own
  `router.py`, `schemas.py`, `models.py`, `service.py`, `dependencies.py`, `config.py`,
  `constants.py`, `exceptions.py`, `utils.py`.
- App composition in [src/main.py](src/main.py): `lifespan` initializes Firebase, CORS
  middleware, a global `AppException` handler, and routers mounted under `/api/v1`.
  Docs (`/docs`) are hidden unless `APP_ENVIRONMENT` is in `{local, staging}`.
- Auth flow ([src/auth/dependencies.py](src/auth/dependencies.py)): the FE sends a Firebase
  ID token as a Bearer header; `get_current_user` verifies it via `firebase_admin` and
  returns a `FirebaseUser`. Use the `CurrentUser` type alias on protected routes. Each
  token-failure mode maps to a specific 401 — never a bare `except Exception`.
- DB layer ([src/database.py](src/database.py)): async engine + `async_sessionmaker`,
  `get_db()` session dependency, a `Base` DeclarativeBase, and the Postgres index
  naming convention. Inject the session with `DbSession = Annotated[AsyncSession, Depends(get_db)]`.
- Config is split per domain (one `BaseSettings` each): global `APP_` prefix
  ([src/config.py](src/config.py)), `FIREBASE_` ([src/auth/config.py](src/auth/config.py)),
  `DATABASE_URL` ([src/database.py](src/database.py)), and `PROVIDER_KEY_ENCRYPTION_KEY`
  ([src/settings/config.py](src/settings/config.py)).

**FastAPI conventions — follow [AGENTS.md](AGENTS.md) (the authority for this repo):**
- **Structure:** organize by domain, not by file type. Cross-domain imports use the explicit
  module name (`from src.users import service as user_service`) — never `import *` or deep
  paths like `from src.auth.service.user import ...`.
- **Async routes:** `async def` only for awaitable non-blocking I/O. Never call blocking code
  (`requests`, `time.sleep`, `open()`, sync DB driver) inside `async def` — use the async
  equivalent or `await run_in_threadpool(fn, ...)`. Use plain `def` for unavoidable blocking
  I/O; offload CPU-bound work to a worker.
- **Dependencies:** use `Annotated[T, Depends(...)]`, not default-arg `Depends(...)`. Validate
  inside dependencies (load + check + return) and chain them for reuse. Deps are cached per
  request; prefer `async def` deps.
- **Pydantic v2:** use built-in validators (`EmailStr`, `Field(ge=...)`, `StrEnum`). No
  `json_encoders` (use `@field_serializer`), no `.dict()`, no contradictory
  `Field(ge=18, default=None)`.
- **Database:** SQLAlchemy 2.0 async (`AsyncSession`) only — never a sync session in `async def`.
  snake_case singular tables; `_at`/`_date` suffixes; consistent FK names. Do joins/aggregation
  in SQL, hydrate Pydantic only for response validation.
- **Auth:** `PyJWT` (`import jwt`) if/when JWTs are needed — never `python-jose`.
- **Background work:** `BackgroundTasks` only for <1s fire-and-forget; use Celery/Arq/RQ for
  anything needing retries, scheduling, or that you'd page on.
- **Errors:** catch the specific exception and raise `HTTPException` with a meaningful status —
  never wrap a route body in `except Exception`.
- **Docs:** fully document endpoints (`response_model`, `status_code`, `summary`, `responses`).
- **Testing:** `httpx.AsyncClient` + `ASGITransport`; swap deps with `app.dependency_overrides`,
  not monkeypatching; use a real DB, don't mock it.
- **Migrations:** static, reversible, async template (`alembic init -t async migrations`).
- **Lint:** `ruff check --fix src` + `ruff format src`.

**Developer workflows:**
- Run dev server: `uvicorn src.main:app --reload`
- Lint/format: `ruff check --fix src` then `ruff format src`
- Tests: `pytest` (testpaths = `tests`, asyncio auto mode)
- Migrations: `alembic init -t async migrations`, then `alembic revision --autogenerate` / `alembic upgrade head`

**Key directories:**
- `src/` — application code. Built domains: `src/auth/` (Firebase token verification),
  `src/users/` (canonical profile: `models.py`, `schemas.py`, `service.py`,
  `dependencies.py`), and `src/settings/` (provider-key persistence — see below).
- `src/main.py`, `src/config.py`, `src/database.py`, `src/exceptions.py` — app-level shared modules.
- `alembic.ini` — Alembic config (`script_location = migrations`, dated `file_template`).
- Env vars in `.env`: `DATABASE_URL`, `AI_API_KEY`, `AI_MODEL`, `AI_MAX_TOKENS`,
  `APP_ENVIRONMENT`, `APP_CORS_ORIGINS`, `APP_SECRET_KEY`, `PROVIDER_KEY_ENCRYPTION_KEY`
  (Fernet key — generate with
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
  Firebase credentials are set via individual `FIREBASE_*` vars (`FIREBASE_PROJECT_ID`,
  `FIREBASE_PRIVATE_KEY_ID`, `FIREBASE_PRIVATE_KEY`, `FIREBASE_CLIENT_EMAIL`,
  `FIREBASE_CLIENT_ID`, `FIREBASE_CLIENT_X509_CERT_URL`, plus optional URI/domain fields
  with defaults) — no JSON file is needed. `src/auth/firebase.py` assembles the cert dict
  at startup.

**Lesson-plans domain (built):** `src/lesson_plans/` generates and persists DepEd MATATAG / ILAW
lesson plans. Endpoints (mounted under `/api/v1`, all require `CurrentDbUser`): `POST /lesson-plans`
(generate via the user's active provider + save → `201` `LessonPlanDetail`), `GET /lesson-plans`
(list summaries, newest first), `GET /lesson-plans/{id}`, `DELETE /lesson-plans/{id}` (`204`).
Generation is **provider-agnostic over raw `httpx`** (no provider SDKs): `service.generate_and_save`
resolves the active provider + decrypted key via `settings_service.get_active_provider_key`, builds
messages from `prompts.py` (`LESSON_PLAN_SYSTEM_PROMPT` + `build_lesson_plan_user_message`), calls
`providers.generate_json` (Gemini `generateContent` with `responseMimeType=application/json`; Grok
OpenAI-compatible `chat/completions` with `response_format` json_schema), validates the JSON against
the `GeneratedLessonPlan` Pydantic model, then **overrides deterministic fields** (header,
signatories, session labels, `[Teacher to complete]` reflections, per-session array lengths) from the
request. Per-provider model IDs/URLs/timeout are env-overridable in `config.py` (`LESSON_PLAN_*`;
defaults `gemini-2.5-flash` / `grok-3`). Domain exceptions (`exceptions.py`) map to `409`
(no key configured), `502` (provider error / invalid response). Table `lesson_plan` (denormalized
header columns + `plan_json` JSONB, FK→`user.id` `CASCADE`) via
`migrations/versions/2026-06-26_create_lesson_plan_table.py`. `migrations/env.py` now imports the
settings + lesson_plans models so autogenerate sees every table. The legacy `AI_*` env vars are
Anthropic leftovers and are unused.

**Auth ↔ users wiring (built):** the FE registers via `POST /api/v1/auth/register` and loads the
profile via `GET /api/v1/auth/user/{uid}`. `src/users/schemas.py` uses a **camelCase alias
generator** (`alias_generator=to_camel`, `populate_by_name=True`, `from_attributes=True`) so JSON
matches the FE's camelCase `User`/`RegisterInput`; the DB stays snake_case. The `user` table is
created by `migrations/versions/2026-06-25_create_user_table.py`. **No team concept** (removed).

**Settings domain (built):** `src/settings/` persists AI-provider API keys scoped to the
authenticated Firebase user. Endpoints: `GET /api/v1/settings/provider-keys` (masked/write-only
— returns `configured` flag + masked preview, never the raw key) and
`PATCH /api/v1/settings/provider-keys` (partial update — `activeProvider`, and per-provider
key map where `""` clears the key). Keys are encrypted at rest with Fernet
(`cryptography>=42.0`). Tables: `provider_setting` (active-provider preference per user) and
`provider_key` (encrypted key per user+provider, UNIQUE(user_id, provider)), both FK→`user.id`
with `ondelete="CASCADE"`. Migration: `migrations/versions/2026-06-26_create_provider_keys_tables.py`.
The `CurrentDbUser` dependency (`src/users/dependencies.py`) resolves a Firebase token to the
DB `User` row; reuse it in future domains (e.g. `src/lesson_plans/`) that need the UUID.

> **Missing / incomplete information — please confirm with the user before relying on it:**
> - `src/lesson_plans/` is now **built** and mounted in [src/main.py](src/main.py) (see the
>   Lesson-plans domain above).
> - No `tests/` directory exists yet despite being configured.
> - Migrations exist (`migrations/env.py` is async and sources `DATABASE_URL` from
>   `src.database.db_settings`), but require a reachable Postgres + installed deps to run
>   (`alembic upgrade head`); the new `lesson_plan` migration has not been applied in this
>   environment.
> - Generation uses the user's **active provider (Gemini or Grok)** over `httpx`, not Anthropic;
>   the legacy `AI_API_KEY` / `AI_MODEL` / `AI_MAX_TOKENS` env vars are unused. Per-provider
>   settings live in `src/lesson_plans/config.py` (`LESSON_PLAN_*`, all defaulted).
> - Firebase credentials are now supplied via individual `FIREBASE_*` env vars; no JSON
>   service-account file is needed. Fill in the real values in `.env` before running.

</project-context>

### Critical Rules

- When working on this project, prioritize code readability and maintainability.
- Keep functions and components small and focused on a single responsibility.
- Apply KISS (Keep It Simple, Stupid) and YAGNI (You Aren't Gonna Need It) principles.
- Absolutely do not modify any other part of the file except the <project-context> section when updating project context.
- Ask clarifying questions before making significant architectural changes.
- Never change the `.env` or configuration files unless explicitly instructed.
- When referencing files, include line numbers for specific sections when applicable.

### Context Management

- Focus suggestions on the current file and its immediate dependencies.
- Reference other files explicitly when cross-file changes are needed.

### Inline Patterns

- Use `// TODO:` or `# TODO:` to indicate where implementations are needed
- Use `// Example:` or `# Example:` to guide expected output format
- Use `// Note:` or `# Note:` for important constraints and considerations

### Code Style Preferences

- Use consistent naming (camelCase for JS, snake_case for DB).
- Prefer composition over inheritance.
- Add JSDoc for public APIs.
- Always apply docstring.

### On Every Code Change

- Always use context7 and sonarqube MCPs when available.
- Update <project-context> section in the `CLAUDE.md` file to reflect any changes in tech stack, project structure, or critical commands.
- Ensure functions and components are grouped logically into specific modules, files, or folders based on their purpose.
- In each file or module, include a brief comment at the top summarizing its purpose and functionality.
- In each function or component, include a brief comment summarizing its purpose, inputs, outputs, and side effects.
- Always handle errors and edge cases gracefully, providing meaningful messages or fallbacks.

### If Unsure

- If context is unclear, ask for a specific file to reference and expand the example with line-numbered snippets.

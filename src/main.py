from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth.router import router as auth_router
from src.config import app_settings
from src.curriculum.router import router as curriculum_router
from src.exceptions import AppException, app_exception_handler
from src.lesson_plans.router import router as lesson_plans_router
from src.settings.router import router as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.auth.firebase import init_firebase

    init_firebase()
    yield


SHOW_DOCS_IN = {"local", "staging"}
app_kwargs: dict = {"title": "Lesson Plan Generator API", "lifespan": lifespan}
if app_settings.ENVIRONMENT not in SHOW_DOCS_IN:
    app_kwargs["openapi_url"] = None

app = FastAPI(**app_kwargs)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]

app.include_router(auth_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(lesson_plans_router, prefix="/api/v1")
app.include_router(curriculum_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

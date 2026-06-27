"""FastAPI application entry point — Extract API + web UI."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src import __version__
from src.api.routes import ai, convert, jobs
from src.config import JOBS_DIR
from src.job_cleanup import cleanup_old_jobs

logger = logging.getLogger(__name__)


def _cors_origins() -> list[str]:
    raw = os.environ.get(
        "EXTRACT_CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173,https://beaver20007.github.io",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_old_jobs()
    yield
    cleanup_old_jobs()

EXTRACT_ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = EXTRACT_ROOT / "static"

app = FastAPI(title="magical-pdf-extract", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs.router)
app.include_router(ai.router)
app.include_router(convert.router)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

JOBS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/")
def extract_ui() -> FileResponse:
    """Extract web UI (Phase 5.2/5.3)."""
    index = STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(404, "UI not found; use /docs for API")
    return FileResponse(index, media_type="text/html; charset=utf-8")


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "magical-pdf-extract",
        "version": __version__,
        "public_beta": os.environ.get("EXTRACT_PUBLIC_BETA", "").lower() in ("1", "true", "yes"),
    }

"""FastAPI application entry point — Extract API + web UI."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src import __version__
from src.api.routes import jobs
from src.config import JOBS_DIR

EXTRACT_ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = EXTRACT_ROOT / "static"

app = FastAPI(title="magical-pdf-extract", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "https://beaver20007.github.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs.router)

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
def health() -> dict[str, str]:
    return {"status": "ok", "service": "magical-pdf-extract", "version": __version__}

"""FastAPI application entry point."""

from fastapi import FastAPI

from src import __version__
from src.api.routes import jobs
from src.config import JOBS_DIR

app = FastAPI(title="ocr-docs", version=__version__)
app.include_router(jobs.router)

JOBS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ocr-docs", "version": __version__}

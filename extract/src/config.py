"""Runtime configuration from environment."""

from __future__ import annotations

import os
from pathlib import Path

EXTRACT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = EXTRACT_ROOT
DATA_DIR = Path(os.environ.get("OCR_DOCS_DATA_DIR", EXTRACT_ROOT / "data"))
JOBS_DIR = DATA_DIR / "jobs"

MAX_BYTES = int(os.environ.get("OCR_DOCS_MAX_BYTES", 52_428_800))  # 50 MB
MAX_PAGES = int(os.environ.get("OCR_DOCS_MAX_PAGES", 100))
JOB_TIMEOUT = int(os.environ.get("OCR_DOCS_JOB_TIMEOUT", 300))
DEFAULT_LANGUAGES = os.environ.get("OCR_DOCS_LANGUAGES", "ru,en").split(",")

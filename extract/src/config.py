"""Runtime configuration from environment."""

from __future__ import annotations

import os
from pathlib import Path

EXTRACT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = EXTRACT_ROOT
DATA_DIR = Path(os.environ.get("OCR_DOCS_DATA_DIR", EXTRACT_ROOT / "data"))
JOBS_DIR = DATA_DIR / "jobs"

_PUBLIC_BETA = os.environ.get("EXTRACT_PUBLIC_BETA", "").lower() in ("1", "true", "yes")
_DEFAULT_MAX_BYTES = 20_971_520 if _PUBLIC_BETA else 52_428_800  # 20 MB beta / 50 MB local
_DEFAULT_MAX_PAGES = 15 if _PUBLIC_BETA else 100

MAX_BYTES = int(os.environ.get("OCR_DOCS_MAX_BYTES", _DEFAULT_MAX_BYTES))
MAX_PAGES = int(os.environ.get("OCR_DOCS_MAX_PAGES", _DEFAULT_MAX_PAGES))
JOB_TIMEOUT = int(os.environ.get("OCR_DOCS_JOB_TIMEOUT", 300))
DEFAULT_LANGUAGES = os.environ.get("OCR_DOCS_LANGUAGES", "ru,en").split(",")

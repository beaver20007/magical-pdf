"""Runtime configuration from environment."""

from __future__ import annotations

import os
from pathlib import Path

EXTRACT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = EXTRACT_ROOT
DATA_DIR = Path(os.environ.get("OCR_DOCS_DATA_DIR", EXTRACT_ROOT / "data"))
JOBS_DIR = DATA_DIR / "jobs"

def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes")


PUBLIC_BETA = _env_bool("EXTRACT_PUBLIC_BETA", False)
_DEFAULT_MAX_BYTES = 20_971_520 if PUBLIC_BETA else 52_428_800  # 20 MB beta / 50 MB local
_DEFAULT_MAX_PAGES = 10 if PUBLIC_BETA else 100

MAX_BYTES = int(os.environ.get("OCR_DOCS_MAX_BYTES", _DEFAULT_MAX_BYTES))
MAX_PAGES = int(os.environ.get("OCR_DOCS_MAX_PAGES", _DEFAULT_MAX_PAGES))
JOB_TIMEOUT = int(os.environ.get("OCR_DOCS_JOB_TIMEOUT", 900 if PUBLIC_BETA else 300))
DEFAULT_BATCH_PAGES = int(os.environ.get("OCR_DOCS_BATCH_PAGES", 2 if PUBLIC_BETA else 4))
SUPPLEMENT_OCR = _env_bool("OCR_DOCS_SUPPLEMENT_OCR", not PUBLIC_BETA)
PAGE_BG_DPI = int(os.environ.get("OCR_DOCS_PAGE_BG_DPI", 120 if PUBLIC_BETA else 150))
MAX_CONCURRENT_JOBS = int(os.environ.get("OCR_DOCS_MAX_CONCURRENT_JOBS", 1 if PUBLIC_BETA else 2))
DEFAULT_LANGUAGES = os.environ.get("OCR_DOCS_LANGUAGES", "ru,en").split(",")

# Spelling/grammar: off on public beta (privacy + rate limits). Local dev: on by default.
SPELL_CORRECT = _env_bool("OCR_DOCS_SPELL_CORRECT", not PUBLIC_BETA)
GRAMMAR_CORRECT = _env_bool("OCR_DOCS_GRAMMAR_CORRECT", not PUBLIC_BETA)
SSL_VERIFY = _env_bool("OCR_DOCS_SSL_VERIFY", False)

# ─── AI (Phase 8) ────────────────────────────────────────────
ANTHROPIC_API_KEY: str | None = os.environ.get("ANTHROPIC_API_KEY")
AI_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
AI_MAX_INPUT_CHARS = int(os.environ.get("AI_MAX_INPUT_CHARS", 80_000))

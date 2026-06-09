"""Remove old job directories to limit disk use on public beta."""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path

from src.config import JOBS_DIR

logger = logging.getLogger(__name__)


def cleanup_old_jobs(*, max_age_hours: int | None = None) -> int:
    ttl = max_age_hours
    if ttl is None:
        ttl = int(os.environ.get("OCR_DOCS_JOB_TTL_HOURS", "0"))
    if ttl <= 0 or not JOBS_DIR.is_dir():
        return 0

    cutoff = time.time() - ttl * 3600
    removed = 0
    for job_dir in JOBS_DIR.iterdir():
        if not job_dir.is_dir():
            continue
        try:
            if job_dir.stat().st_mtime < cutoff:
                shutil.rmtree(job_dir, ignore_errors=True)
                removed += 1
        except OSError as exc:
            logger.warning("Failed to remove job %s: %s", job_dir.name, exc)
    return removed

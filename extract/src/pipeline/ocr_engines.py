from __future__ import annotations

import logging
import threading
from typing import Optional

from PIL import Image

try:
    from src.pipeline.emit_pptx_slides import OcrWord, _run_tesseract as _tess_run
    _HAS_TESSERACT = True
except Exception:
    try:
        import collections
        OcrWord = collections.namedtuple("OcrWord", ["text", "px0", "py0", "px1", "py1", "conf"])
    except Exception:
        pass
    _HAS_TESSERACT = False

try:
    import easyocr as _easyocr_mod
    _HAS_EASYOCR = True
except ImportError:
    _easyocr_mod = None  # type: ignore[assignment]
    _HAS_EASYOCR = False

try:
    from paddleocr import PaddleOCR as _PaddleOCR
    _HAS_PADDLEOCR = True
except ImportError:
    _PaddleOCR = None  # type: ignore[assignment]
    _HAS_PADDLEOCR = False

ENGINES_AVAILABLE: dict[str, bool] = {
    "tesseract": _HAS_TESSERACT,
    "easyocr": _HAS_EASYOCR,
    "paddleocr": _HAS_PADDLEOCR,
}

_log = logging.getLogger(__name__)

_lock = threading.Lock()
_easyocr_reader: Optional[object] = None
_paddleocr_instance: Optional[object] = None


def _get_easyocr_reader() -> object:
    global _easyocr_reader
    if _easyocr_reader is None:
        with _lock:
            if _easyocr_reader is None:
                _easyocr_reader = _easyocr_mod.Reader(["ru", "en"], gpu=False)
    return _easyocr_reader


def _get_paddleocr() -> object:
    global _paddleocr_instance
    if _paddleocr_instance is None:
        with _lock:
            if _paddleocr_instance is None:
                import logging as _logging
                _logging.getLogger("ppocr").setLevel(_logging.ERROR)
                _paddleocr_instance = _PaddleOCR(lang="ru", use_angle_cls=True)
    return _paddleocr_instance


def run_tesseract(img: Image.Image) -> list[OcrWord]:
    if not _HAS_TESSERACT:
        return []
    return _tess_run(img, psm=11, up_scale=1.0)


def run_easyocr(img: Image.Image) -> list[OcrWord]:
    if not _HAS_EASYOCR:
        return []
    import numpy as _np
    reader = _get_easyocr_reader()
    raw = reader.readtext(_np.array(img))
    words: list[OcrWord] = []
    for bbox_points, text, conf in raw:
        text = (text or "").strip()
        if not text:
            continue
        x0 = int(min(p[0] for p in bbox_points))
        y0 = int(min(p[1] for p in bbox_points))
        x1 = int(max(p[0] for p in bbox_points))
        y1 = int(max(p[1] for p in bbox_points))
        words.append(OcrWord(text=text, px0=x0, py0=y0, px1=x1, py1=y1, conf=float(conf)))
    return words


def run_paddleocr(img: Image.Image) -> list[OcrWord]:
    if not _HAS_PADDLEOCR:
        return []
    import numpy as _np
    ocr = _get_paddleocr()
    raw = ocr.ocr(img, cls=True)
    words: list[OcrWord] = []
    if not raw:
        return words
    for line in raw:
        if not line:
            continue
        for item in line:
            bbox_points, (text, conf) = item
            text = (text or "").strip()
            if not text:
                continue
            x0 = int(min(p[0] for p in bbox_points))
            y0 = int(min(p[1] for p in bbox_points))
            x1 = int(max(p[0] for p in bbox_points))
            y1 = int(max(p[1] for p in bbox_points))
            words.append(OcrWord(text=text, px0=x0, py0=y0, px1=x1, py1=y1, conf=float(conf)))
    return words


def _iou(a: OcrWord, b: OcrWord) -> float:
    ix0 = max(a.px0, b.px0)
    iy0 = max(a.py0, b.py0)
    ix1 = min(a.px1, b.px1)
    iy1 = min(a.py1, b.py1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a = max(1, (a.px1 - a.px0) * (a.py1 - a.py0))
    area_b = max(1, (b.px1 - b.px0) * (b.py1 - b.py0))
    return inter / (area_a + area_b - inter)


def vote_engines(results: list[list[OcrWord]], iou_threshold: float = 0.4) -> list[OcrWord]:
    all_words: list[OcrWord] = []
    for engine_words in results:
        all_words.extend(engine_words)

    if not all_words:
        return []

    used = [False] * len(all_words)
    groups: list[list[int]] = []

    for i in range(len(all_words)):
        if used[i]:
            continue
        group = [i]
        used[i] = True
        for j in range(i + 1, len(all_words)):
            if not used[j] and _iou(all_words[i], all_words[j]) > iou_threshold:
                group.append(j)
                used[j] = True
        groups.append(group)

    winners: list[OcrWord] = []
    for group in groups:
        if len(group) >= 2:
            best_idx = max(group, key=lambda i: all_words[i].conf)
            w = all_words[best_idx]
            boosted_conf = min(1.0, w.conf + 0.1)
            winners.append(OcrWord(text=w.text, px0=w.px0, py0=w.py0, px1=w.px1, py1=w.py1, conf=boosted_conf))
        else:
            winners.append(all_words[group[0]])

    return sorted(winners, key=lambda w: (w.py0, w.px0))


def ocr_multi(img: Image.Image, engines: list[str] | None = None) -> list[OcrWord]:
    if engines is None:
        engines = ["tesseract", "easyocr"]
        if _HAS_PADDLEOCR:
            engines.append("paddleocr")

    _dispatch = {
        "tesseract": run_tesseract,
        "easyocr": run_easyocr,
        "paddleocr": run_paddleocr,
    }

    results: list[list[OcrWord]] = []
    for name in engines:
        fn = _dispatch.get(name)
        if fn is None:
            _log.warning("ocr_multi: unknown engine %r, skipping", name)
            continue
        try:
            words = fn(img)
            results.append(words)
        except Exception as exc:
            _log.warning("ocr_multi: engine %r failed: %s", name, exc)

    if not results:
        return []

    return vote_engines(results)

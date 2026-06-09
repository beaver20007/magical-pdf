"""Post-OCR text cleanup for Russian legal/business documents."""

from __future__ import annotations

import re

# Common OCR misreads in scanned Russian contracts
_WORD_FIXES: dict[str, str] = {
    "дальнсйшем": "дальнейшем",
    "дальнсйшего": "дальнейшего",
    "КЛУКОЙЛ": "«ЛУКОЙЛ",
    "КЛЕСАВИК": "«ЛЕСАВИК",
    "дождеприемник": "дождеприёмник",
    "дождеприемники": "дождеприёмники",
    "Дожбепрuвмнuк": "Дождеприёмник",
    "ДП-ЗОз0": "ДП-30.30",
    "ДП-303О": "ДП-30.30",
    "ДП-30.3О": "ДП-30.30",
    "Pasi": "Basic",
    "HudcmaBкou": "надставкой",
}


def clean_ocr_text(text: str) -> str:
    if not text or not text.strip():
        return text

    t = text
    for old, new in _WORD_FIXES.items():
        t = t.replace(old, new)

    # № variants: Ng 3, Ne 9, No2024
    t = re.sub(r"\bNg\s*", "№ ", t)
    t = re.sub(r"\bNe\s*", "№ ", t, flags=re.IGNORECASE)
    t = re.sub(r"\bNo(?=\d)", "№", t)

    # <l5> / <I5> → 15 (OCR confuses leading 1 with l/I)
    t = re.sub(r"<[lI](\d)>", r"1\1", t)

    # Angle brackets used as quotes: <ЛУКОЙЛ-...> → «...»
    t = re.sub(r"<([^<>]{2,})>", r"«\1»", t)

    # Collapse multiple spaces
    t = re.sub(r" {2,}", " ", t)

    return t.strip()

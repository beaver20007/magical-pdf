"""Post-OCR spelling and grammar correction for Russian text blocks."""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

import requests

from src.config import GRAMMAR_CORRECT, SPELL_CORRECT, SSL_VERIFY
from src.pipeline.cleanup import clean_ocr_text
from src.pipeline.ir import DocumentIR, TableBlock, TextBlock

logger = logging.getLogger(__name__)

_SPELLER_URL = "https://speller.yandex.net/services/spellservice.json/checkText"
_LT_URL = "https://api.languagetool.org/v2/check"
_MIN_WORD_LEN = 3
_SPELLER_CHUNK = 7500
_REQUEST_TIMEOUT = 25

# Latin letters often confused with Cyrillic in OCR
_LATIN_TO_CYR = str.maketrans(
    {
        "A": "А",
        "B": "В",
        "C": "С",
        "E": "Е",
        "H": "Н",
        "K": "К",
        "M": "М",
        "O": "О",
        "P": "Р",
        "T": "Т",
        "X": "Х",
        "Y": "У",
        "a": "а",
        "c": "с",
        "e": "е",
        "o": "о",
        "p": "р",
        "x": "х",
        "y": "у",
    }
)

_speller_cache: dict[str, str] = {}


def _cyrillic_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    cyr = sum(1 for ch in letters if "\u0400" <= ch <= "\u04FF")
    return cyr / len(letters)


def fix_mixed_script(text: str) -> str:
    """Replace Latin lookalikes when line is mostly Cyrillic."""
    if _cyrillic_ratio(text) < 0.55:
        return text
    return text.translate(_LATIN_TO_CYR)


def _fix_punctuation(text: str) -> str:
    t = re.sub(r"\s+([,.;:!?])", r"\1", text)
    t = re.sub(r"([,.;:!?])([^\s\d])", r"\1 \2", t)
    return re.sub(r" {2,}", " ", t).strip()


def _apply_speller_errors(text: str, errors: list[dict[str, Any]]) -> str:
    if not errors:
        return text
    out = text
    for err in sorted(errors, key=lambda e: e["pos"], reverse=True):
        word = err.get("word", "")
        suggestions = err.get("s") or []
        if not suggestions or suggestions[0] == word:
            continue
        pos, length = int(err["pos"]), int(err["len"])
        replacement = suggestions[0]
        out = out[:pos] + replacement + out[pos + length :]
    return out


def _yandex_speller(text: str) -> str:
    key = text.strip().lower()
    if key in _speller_cache:
        return _speller_cache[key]

    try:
        resp = requests.get(
            _SPELLER_URL,
            params={"text": text, "lang": "ru", "options": 512},
            timeout=_REQUEST_TIMEOUT,
            verify=SSL_VERIFY,
        )
        resp.raise_for_status()
        fixed = _apply_speller_errors(text, resp.json())
    except Exception as exc:
        logger.warning("Yandex Speller skipped: %s", exc)
        fixed = text

    _speller_cache[key] = fixed
    return fixed


def _apply_lt_matches(text: str, matches: list[dict[str, Any]]) -> str:
    out = text
    for match in sorted(matches, key=lambda m: m["offset"], reverse=True):
        reps = match.get("replacements") or []
        if not reps:
            continue
        offset = int(match["offset"])
        length = int(match["length"])
        out = out[:offset] + reps[0]["value"] + out[offset + length :]
    return out


def _language_tool(text: str) -> str:
    if len(text) < _MIN_WORD_LEN:
        return text
    try:
        resp = requests.post(
            _LT_URL,
            data={"language": "ru-RU", "text": text, "enabledOnly": "false"},
            timeout=_REQUEST_TIMEOUT,
            verify=SSL_VERIFY,
        )
        resp.raise_for_status()
        matches = resp.json().get("matches") or []
        # Skip style-only hints; keep spelling/grammar
        actionable = [
            m
            for m in matches
            if m.get("replacements")
            and m.get("ruleIssueType") in (None, "misspelling", "grammar", "typographical")
        ]
        if not actionable:
            actionable = [m for m in matches if m.get("replacements")]
        return _apply_lt_matches(text, actionable)
    except Exception as exc:
        logger.warning("LanguageTool skipped: %s", exc)
        return text


def _local_fixes(text: str) -> str:
    t = clean_ocr_text(text)
    t = fix_mixed_script(t)
    return _fix_punctuation(t)


def correct_line(text: str, *, use_spell: bool = True, use_grammar: bool = True) -> str:
    if not text or not text.strip():
        return text

    t = _local_fixes(text)

    if use_spell and "ru" in _active_langs_hint():
        t = _yandex_speller(t)
        time.sleep(0.05)

    if use_grammar and len(t) >= _MIN_WORD_LEN:
        t = _language_tool(t)
        time.sleep(0.08)

    return t.strip()


_active_langs: list[str] = ["ru", "en"]


def _active_langs_hint() -> list[str]:
    return _active_langs


def correct_document_text(
    ir: DocumentIR,
    languages: list[str] | None = None,
    *,
    use_spell: bool | None = None,
    use_grammar: bool | None = None,
) -> int:
    """Correct all text blocks and table cells. Returns number of changed snippets."""
    global _active_langs
    _active_langs = languages or ir.source.languages or ["ru", "en"]

    spell = SPELL_CORRECT if use_spell is None else use_spell
    grammar = GRAMMAR_CORRECT if use_grammar is None else use_grammar

    changed = 0
    for block in ir.blocks:
        if isinstance(block, TextBlock) and block.text.strip():
            new_text = correct_line(block.text, use_spell=spell, use_grammar=grammar)
            if new_text != block.text:
                block.text = new_text
                changed += 1
        elif isinstance(block, TableBlock):
            for ri, row in enumerate(block.rows):
                for ci, cell in enumerate(row):
                    if not str(cell).strip():
                        continue
                    new_cell = correct_line(str(cell), use_spell=spell, use_grammar=grammar)
                    if new_cell != cell:
                        block.rows[ri][ci] = new_cell
                        changed += 1

    if changed:
        ir.meta.warnings.append(f"text correct: updated {changed} snippets (spell={spell}, grammar={grammar})")
    return changed

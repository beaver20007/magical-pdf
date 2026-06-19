"""
emit_pptx_slides.py — конвертация slide-PDF в PPTX с редактируемым текстом.

Архитектура (v5):
  1. Рендерим страницу в PNG
  2. Вырезаем каждый image-блок (чертёж, иллюстрацию) как отдельный кроп
  3. На кропе запускаем EasyOCR → находим текстовые области внутри изображения
  4. В кропе замазываем OCR-области цветом фона (убираем текст из растра)
  5. Вектор-слой страницы (без текста и без image-blocks) — отдельный PNG
  6. В PPTX:
       - Фон слайда (цвет страницы)
       - Вектор-слой (линии, рамки, декор)
       - Каждый кроп на своей позиции (замазанный — только графика без текста)
       - Text boxes из native PDF text
       - Text boxes из OCR поверх каждого кропа (на координатах кропа)
  Результат: весь текст редактируем, включая надписи внутри чертежей.
"""
from __future__ import annotations

from pathlib import Path
from statistics import mode as stat_mode
from typing import NamedTuple

import fitz
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Pt

try:
    from src.pipeline.ocr_cache import load_ocr_cache as _load_ocr_cache, save_ocr_cache as _save_ocr_cache
    _HAS_OCR_CACHE = True
except Exception:
    _HAS_OCR_CACHE = False

_PT_TO_EMU = 12700

_TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _emu(pt: float) -> int:
    return int(pt * _PT_TO_EMU)


# ── Цвет фона ────────────────────────────────────────────────────────────────

def _dominant_color(
    img: Image.Image, x0: int, y0: int, x1: int, y1: int, band: int = 8
) -> tuple[int, int, int]:
    w, h = img.size
    pixels: list[tuple[int, int, int]] = []
    for px in range(max(0, x0 - band), min(w, x1 + band)):
        for py in [max(0, y0 - band - 1), min(h - 1, y1 + band)]:
            pixels.append(img.getpixel((px, py))[:3])
    for py in range(max(0, y0 - band), min(h, y1 + band)):
        for px in [max(0, x0 - band - 1), min(w - 1, x1 + band)]:
            pixels.append(img.getpixel((px, py))[:3])
    if not pixels:
        return (255, 255, 255)
    bucketed = [(r // 32 * 32, g // 32 * 32, b // 32 * 32) for r, g, b in pixels]
    try:
        dom = stat_mode(bucketed)
    except Exception:
        dom = bucketed[0]
    in_bkt = [p for p in pixels if (p[0]//32*32, p[1]//32*32, p[2]//32*32) == dom]
    return (
        sum(p[0] for p in in_bkt) // len(in_bkt),
        sum(p[1] for p in in_bkt) // len(in_bkt),
        sum(p[2] for p in in_bkt) // len(in_bkt),
    )


def _page_bg_color(img: Image.Image) -> tuple[int, int, int]:
    w, h = img.size
    corners = [(2, 2), (w-3, 2), (2, h-3), (w-3, h-3)]
    colors = [img.getpixel(c)[:3] for c in corners]
    return (
        sum(c[0] for c in colors) // 4,
        sum(c[1] for c in colors) // 4,
        sum(c[2] for c in colors) // 4,
    )


def _mask_rects(
    img: Image.Image,
    rects_px: list[tuple[int, int, int, int]],
    fill: tuple[int, int, int] | None = None,
    pad: int = 2,
) -> Image.Image:
    """Замазываем прямоугольники (px) цветом фона или заданным цветом."""
    img = img.copy()
    draw = ImageDraw.Draw(img)
    iw, ih = img.size
    for x0, y0, x1, y1 in rects_px:
        px0 = max(0, x0 - pad)
        py0 = max(0, y0 - pad)
        px1 = min(iw, x1 + pad)
        py1 = min(ih, y1 + pad)
        if px1 <= px0 or py1 <= py0:
            continue
        c = fill if fill else _dominant_color(img, px0, py0, px1, py1)
        draw.rectangle([px0, py0, px1, py1], fill=c)
    return img


def _pt_rects_to_px(
    rects_pt: list[tuple], scale: float
) -> list[tuple[int, int, int, int]]:
    return [
        (int(x0*scale), int(y0*scale), int(x1*scale), int(y1*scale))
        for x0, y0, x1, y1 in rects_pt
    ]


# ── OCR на кропе ─────────────────────────────────────────────────────────────

class OcrWord(NamedTuple):
    text: str
    # Координаты в пикселях КРОПА
    px0: int
    py0: int
    px1: int
    py1: int
    conf: float


import re as _re
_ALPHANUM      = _re.compile(r"[А-Яа-яёЁA-Za-z0-9]")
_CYRILLIC      = _re.compile(r"[А-Яа-яёЁ]")
# "чистые" символы — всё что может быть в реальной аннотации чертежа
_CLEAN_ALNUM   = _re.compile(r"[А-Яа-яёЁA-Za-z0-9\-—.,:%°+=()①-⑨₁-₉/\\]")
_NOISE         = _re.compile(r"^[|\\/*+=(){}\[\]<>«»\"\'`^~@#$%&]{1,2}$")
# Паттерны измерительных значений: —0.36, -1.13, ±0.05, .30 (ведущая точка), =0.36
_MEASUREMENT   = _re.compile(r"^([—\-±=]?\d+[.,]\d+|[.,]\d+)$")
# Технические обозначения чертежей: i=4%, 1:200, 0.5%, уклон-значения
_TECH_MARKER   = _re.compile(r"^(i=[0-9]+%?|[0-9]+:[0-9]+|[0-9]+[.,][0-9]+%|[А-Яа-яёЁ]{2,10}[0-9]*)$")
# Штриховка читается как короткие латинские "слова" из e,s,a,f,t,i,c (без кириллицы/цифр)
# Строчные латинские слова ≤5 символов — штриховка (ah, ar, ee, jam, tum, bema).
# Заглавные (Dn, PP) и смешанные не попадают под этот фильтр.
_SHORT_LOWER_LAT = _re.compile(r"^[a-z]{2,5}[).,!|]*$")
# Полностью заглавные латинские слова >=3 букв — OCR мусор (ALN, ALY, GRE, RAS, ALLY…)
# 2-буквенные (PP, DN, SS, CA) обрабатываются отдельно в inline-фильтре
_ALL_CAPS_LATIN  = _re.compile(r"^[A-Z]{3,}$")
_DASH_SEQ        = _re.compile(r'^[\-—<>/\\]{2,6}$')
_TECH_WHITELIST = frozenset({
    'мм', 'см', 'дм', 'км', 'кг', 'шт', 'пм', 'пл', 'вп', 'ту',
    'пвх', 'пп', 'дп', 'бв', 'пу', 'ду', 'дн', 'кн', 'мн', 'па',
    'dn', 'pp', 'pe', 'kg', 'mm', 'cm', 'wt', 'kw', 'hz', 'pvc',
})


def _apply_char_subs(text: str) -> str:
    """
    Исправляет кириллические буквы, ошибочно распознанные в числовом контексте.
    О/о → 0 рядом с цифрами/точкой, З → 3 рядом с цифрами.
    """
    t = text
    # Кириллическая О/о между цифрами или знаками пунктуации (.,)
    t = _re.sub(r'(?<=[.,\d])[Оо](?=[.,\d])', '0', t)
    # Кириллическая О/о в начале числа
    t = _re.sub(r'^[Оо](?=[.,\d])', '0', t)
    # Кириллическая О/о в конце числа
    t = _re.sub(r'(?<=[.,\d])[Оо]$', '0', t)
    # Кириллическая З между цифрами
    t = _re.sub(r'(?<=[\d])З(?=[\d])', '3', t)
    # Кириллическая З в начале числа
    t = _re.sub(r'^З(?=[.,\d])', '3', t)
    return t


def _is_valid_ocr(text: str) -> bool:
    """
    Принимаем OCR-результат если:
    - длина >= 1 (одиночный маркер типа B, C, А)
    - содержит хотя бы 1 кириллическую/латинскую букву или цифру
    - не является пунктуационным мусором или штриховочным шумом
    - ≥ 40% символов — "чистые"
    """
    t = text.strip()
    if t.lower() in _TECH_WHITELIST:
        return True
    if not t:
        return False
    # Одиночный символ — только размерный маркер (заглавная буква или цифра)
    if len(t) == 1:
        return bool(_re.match(r"[А-ЯA-Z0-9]", t))
    if not _ALPHANUM.search(t):
        return False
    if _NOISE.match(t):
        return False
    if _DASH_SEQ.match(t) and not _ALPHANUM.search(t):
        return False
    # Строчные латинские слова ≤5 символов без цифр/кириллицы — штриховка или мусор
    if _SHORT_LOWER_LAT.match(t) and not _CYRILLIC.search(t) and not _re.search(r"\d", t):
        return False
    # Длинные (>8 символов) латинские слова без кириллицы и цифр — OCR мусор
    # (tlecxoynoeumens, Tlecxoynoeumens) — не могут быть реальными словами в рус. чертеже
    if len(t) > 10 and t.isalpha() and not _CYRILLIC.search(t):
        return False
    # Слова оканчивающиеся на }]| — рамки таблиц (ints}, Lda])
    if t[-1] in ('}', ']', '|') and not _CYRILLIC.search(t) and len(t) <= 8:
        return False
    # Полностью заглавные латинские слова ≥4 букв без кириллицы — OCR мусор (NALLY, ALLY)
    if _ALL_CAPS_LATIN.match(t) and not _CYRILLIC.search(t):
        return False
    # Фильтруем акцентный мусор (ées, éée): доля "чистых" символов ≥ 40%
    no_space = t.replace(" ", "")
    if no_space:
        clean_count = sum(1 for c in no_space if _CLEAN_ALNUM.match(c))
        if clean_count / len(no_space) < 0.40:
            return False
    return True


def _min_conf_for(text: str) -> int:
    """Минимальный confidence в зависимости от типа текста."""
    t = text.strip()
    if text.strip().lower() in _TECH_WHITELIST:
        return 30
    if len(t) == 1:
        return 80   # одиночные символы — только при высокой уверенности
    if _MEASUREMENT.match(t):
        return 20   # числа-измерения — очень низкий порог, сложный фон на чертежах
    if _TECH_MARKER.match(t):
        return 20   # технические маркеры: i=4%, 1:200, уклон
    if _re.match(r"^\d{1,4}$", t):
        return 25   # целые числа (размеры, диаметры) — чуть выше порог от мусора
    if len(t) <= 2:
        if _re.match(r'^[а-яёa-z]{2}$', t):
            return 70   # 2-char строчные фрагменты (ух, ен, oe) — повышенный порог
        return 50   # короткие аббревиатуры (заглавные, смешанные)
    return 28       # всё остальное


def _remove_hatching(gray_arr) -> object:
    """
    Морфологическое opening (PIL) для удаления штриховки.
    Штриховка = тонкие линии (~1-3px); текст = более толстые штрихи (~5-15px).
    Opening (эрозия→дилатация) убирает тонкие объекты, сохраняет толстые.
    """
    import numpy as np
    from PIL import Image as _PILImg, ImageFilter

    pil = _PILImg.fromarray(gray_arr.astype("uint8"))
    # Инвертируем: чёрный текст → белый (для min/max filter)
    inv = _PILImg.fromarray(255 - np.array(pil))
    # Opening: MinFilter (эрозия) затем MaxFilter (дилатация)
    kernel = 5  # размер ядра > толщина штриховки
    eroded  = inv.filter(ImageFilter.MinFilter(kernel))
    dilated = eroded.filter(ImageFilter.MaxFilter(kernel))
    # Инвертируем обратно: белый фон, чёрный текст
    result = _PILImg.fromarray(255 - np.array(dilated))
    return np.array(result)


def _make_gray_variants(crop_img: Image.Image) -> list[tuple[Image.Image, float]]:
    """
    Возвращает несколько вариантов препроцессинга:
    1. Luminosity-grayscale + контраст + 2x upscale
    2. Min(R,G,B) + контраст + 2x upscale — цветной текст (синий, красный) становится чёрным
    Всегда 2x upscale чтобы 4-6pt аннотации (≈20px native) стали ≥40px для Tesseract.
    """
    from PIL import ImageEnhance
    import numpy as _np

    w, h = crop_img.size
    # Для больших изображений уменьшаем масштаб чтобы не съесть всю RAM
    # Tesseract работает хорошо при 150-300 DPI; нативные PDF-изображения уже ~150 DPI
    MAX_DIM = 3000
    if max(w, h) * 2 > MAX_DIM:
        UPSCALE = max(1, MAX_DIM // max(w, h))
    else:
        UPSCALE = 2
    if UPSCALE < 1:
        UPSCALE = 1
    results: list[tuple[Image.Image, float]] = []

    def _up(img: Image.Image) -> Image.Image:
        if UPSCALE == 1:
            return img
        return img.resize((w * UPSCALE, h * UPSCALE), Image.LANCZOS)

    # Вариант 1: стандартный grayscale
    g1 = ImageEnhance.Contrast(crop_img.convert("L")).enhance(2.5)
    results.append((_up(g1).convert("RGB"), float(UPSCALE)))

    # Вариант 2: min(R,G,B) — любой насыщенный цвет → чёрный
    arr = _np.array(crop_img.convert("RGB"))
    min_ch = _np.min(arr, axis=2).astype(_np.uint8)
    g2 = ImageEnhance.Contrast(Image.fromarray(min_ch)).enhance(2.0)
    results.append((_up(g2).convert("RGB"), float(UPSCALE)))

    # Вариант 3: выравнивание гистограммы (ImageOps.equalize) — усиливает низкоконтрастный текст
    from PIL import ImageOps
    g3 = ImageOps.equalize(crop_img.convert("L"))
    g3 = ImageEnhance.Contrast(g3).enhance(1.8)
    results.append((_up(g3).convert("RGB"), float(UPSCALE)))

    # Вариант 4: для плотной штриховки — сильное морфологическое opening (kernel=9)
    # Определяем наличие плотной штриховки по дисперсии пикселей (высокая плотность градиентов).
    gray_arr4 = _np.array(crop_img.convert("L"))
    _variance = float(_np.var(gray_arr4.astype("float32")))
    # Нормализуем: максимальная теоретическая дисперсия = 128^2 = 16384
    _edge_density = _variance / 16384.0
    if _edge_density > 0.30:
        # Плотная штриховка обнаружена: применяем opening с kernel=9
        from PIL import Image as _PILImg, ImageFilter
        _pil4 = _PILImg.fromarray(gray_arr4.astype("uint8"))
        _inv4 = _PILImg.fromarray(255 - _np.array(_pil4))
        _k9 = 9
        _eroded4 = _inv4.filter(ImageFilter.MinFilter(_k9))
        _dilated4 = _eroded4.filter(ImageFilter.MaxFilter(_k9))
        _opened4 = _PILImg.fromarray(255 - _np.array(_dilated4))
        g4 = ImageEnhance.Contrast(_opened4).enhance(2.0)
        results.append((_up(g4).convert("RGB"), float(UPSCALE)))

    # Вариант 5: локальная адаптивная бинаризация — для сканов с неравномерной подсветкой
    # (тени от сгиба, виньетирование). Глобальный контраст не справляется с локально тёмными зонами.
    # Алгоритм: local_mean = BoxBlur(r=16); pixel < local_mean*0.88 → 0 (чёрный), иначе 255 (белый).
    try:
        import numpy as _np5
        from PIL import ImageFilter as _IF5
        _g5 = crop_img.convert("L")
        _local_mean5 = _g5.filter(_IF5.BoxBlur(16))
        _arr5 = _np5.array(_g5, dtype=_np5.float32)
        _mean5 = _np5.array(_local_mean5, dtype=_np5.float32)
        _bin5 = _np5.where(_arr5 < _mean5 * 0.88, 0, 255).astype(_np5.uint8)
        g5 = Image.fromarray(_bin5)
    except Exception:
        from PIL import ImageFilter as _IF5
        _g5 = crop_img.convert("L")
        _local_mean5 = _g5.filter(_IF5.BoxBlur(16))
        _px5 = list(_g5.getdata())
        _mx5 = list(_local_mean5.getdata())
        _bin5 = bytes([0 if p < m * 0.88 else 255 for p, m in zip(_px5, _mx5)])
        g5 = Image.frombytes("L", _g5.size, _bin5)
    results.append((_up(g5).convert("RGB"), float(UPSCALE)))

    return results


def _run_tesseract(img: Image.Image, psm: int, up_scale: float) -> list[OcrWord]:
    """Запускает Tesseract с заданным psm, возвращает слова в исходных пикселях."""
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD
    cfg = f"--oem 1 --psm {psm} -l rus+eng"
    try:
        data = pytesseract.image_to_data(img, config=cfg, output_type=pytesseract.Output.DICT)
    except Exception as e:
        print(f"    Tesseract psm={psm} error: {e}")
        return []

    iw, ih = img.size  # размер апскейлнутого изображения
    # Максимальный допустимый размер bbox слова (в нативных пикселях).
    # PSM 6 убран, но оставляем разумный лимит на случай аномальных bbox:
    # слово шире 55% или выше 30% изображения — скорее всего артефакт
    max_word_w = iw * 0.55 / up_scale
    max_word_h = ih * 0.30 / up_scale

    words: list[OcrWord] = []
    for j in range(len(data["text"])):
        txt = _apply_char_subs((data["text"][j] or "").strip())
        conf = int(data["conf"][j])
        if not txt or not _is_valid_ocr(txt):
            continue
        if conf < _min_conf_for(txt):
            continue
        x0 = int(data["left"][j] / up_scale)
        y0 = int(data["top"][j] / up_scale)
        x1 = int((data["left"][j] + data["width"][j]) / up_scale)
        y1 = int((data["top"][j] + data["height"][j]) / up_scale)
        # Отбрасываем bbox слишком большого размера (шум без PSM 6)
        if (x1 - x0) > max_word_w or (y1 - y0) > max_word_h:
            continue
        words.append(OcrWord(text=txt, px0=x0, py0=y0, px1=x1, py1=y1, conf=conf / 100.0))
    return words


def _merge_word_lists(base: list[OcrWord], extra: list[OcrWord], tol: int = 8) -> list[OcrWord]:
    """Добавляет слова из extra, которых нет в base (по центру bbox с допуском tol px)."""
    def _center(w: OcrWord):
        return ((w.px0 + w.px1) / 2, (w.py0 + w.py1) / 2)
    existing = [_center(w) for w in base]
    merged = list(base)
    for w in extra:
        cx, cy = _center(w)
        if not any(abs(cx - ex) < tol and abs(cy - ey) < tol for ex, ey in existing):
            merged.append(w)
            existing.append((cx, cy))
    return merged


def _has_dense_text_grid(img: Image.Image) -> bool:
    """
    Определяет плотную текстовую сетку (таблицы, штамп-блоки).
    Два критерия:
    1. >18% тёмных пикселей (значение < 128) от общего числа пикселей.
    2. >= 5 строк пикселей, где >40% пикселей тёмные.
    """
    gray = img.convert("L")
    try:
        import numpy as _np
        arr = _np.array(gray)
        dark_mask = arr < 128
        total = dark_mask.size
        dark_count = int(dark_mask.sum())
        # Критерий 1: общая плотность тёмных пикселей
        if total > 0 and dark_count / total > 0.18:
            return True
        # Критерий 2: количество строк с >40% тёмных пикселей
        row_dark = dark_mask.sum(axis=1)
        row_total = arr.shape[1]
        dense_rows = int((row_dark > row_total * 0.40).sum())
        if dense_rows >= 5:
            return True
    except ImportError:
        # Fallback без numpy
        pixels = list(gray.getdata())
        total = len(pixels)
        if total == 0:
            return False
        dark_count = sum(1 for p in pixels if p < 128)
        if dark_count / total > 0.18:
            return True
        w, h = gray.size
        dense_rows = 0
        for row in range(h):
            row_pixels = pixels[row * w:(row + 1) * w]
            row_dark = sum(1 for p in row_pixels if p < 128)
            if w > 0 and row_dark / w > 0.40:
                dense_rows += 1
        if dense_rows >= 5:
            return True
    return False


def _find_small_regions(words: list[OcrWord]) -> list[tuple[int, int, int, int]]:
    """Находит кластеры маленьких низкоуверенных слов для 4x upscale re-OCR."""
    small = [w for w in words if (w.py1 - w.py0) < 20 and w.conf < 0.60]
    if not small:
        return []
    # Сортируем по px0
    small = sorted(small, key=lambda w: w.px0)
    clusters: list[list[OcrWord]] = []
    cur: list[OcrWord] = [small[0]]
    for w in small[1:]:
        prev = cur[-1]
        prev_cy = (prev.py0 + prev.py1) / 2
        cur_cy  = (w.py0 + w.py1) / 2
        if (w.px0 - prev.px1) < 50 and abs(cur_cy - prev_cy) <= 30:
            cur.append(w)
        else:
            clusters.append(cur)
            cur = [w]
    clusters.append(cur)
    result: list[tuple[int, int, int, int]] = []
    for cl in clusters:
        x0 = min(w.px0 for w in cl) - 8
        y0 = min(w.py0 for w in cl) - 8
        x1 = max(w.px1 for w in cl) + 8
        y1 = max(w.py1 for w in cl) + 8
        result.append((x0, y0, x1, y1))
    return result


def _try_rotated_ocr(crop_img: Image.Image, up_scale: float) -> list[OcrWord]:
    """Пробует OCR с поворотом на 90 и 270 градусов для вертикального текста.
    Возвращает слова с координатами, трансформированными обратно в исходное пространство кропа.
    """
    from PIL import ImageEnhance
    result: list[OcrWord] = []
    for angle in [90, 270]:
        rotated = crop_img.rotate(angle, expand=True)
        g = ImageEnhance.Contrast(rotated.convert("L")).enhance(2.5)
        g_rgb = g.convert("RGB")
        words = _run_tesseract(g_rgb, psm=11, up_scale=up_scale)
        if len(words) < 2:
            continue
        avg_conf = sum(w.conf for w in words) / len(words)
        if avg_conf <= 0.55:
            continue
        rw, rh = rotated.size  # после expand=True: rw=orig_h, rh=orig_w (для 90 и 270)
        transformed: list[OcrWord] = []
        for w in words:
            px0, py0, px1, py1 = w.px0, w.py0, w.px1, w.py1
            if angle == 90:
                # rotate(90, expand=True) поворачивает CCW:
                # rotated.size = (orig_h, orig_w)
                # новые координаты в orig: x' = py0, y' = rh - px1, x1' = py1, y1' = rh - px0
                new_px0 = py0
                new_py0 = rh - px1
                new_px1 = py1
                new_py1 = rh - px0
            else:  # 270
                # rotate(270, expand=True) поворачивает CW:
                # rotated.size = (orig_h, orig_w)
                # новые координаты в orig: x' = rw - py1, y' = px0, x1' = rw - py0, y1' = px1
                new_px0 = rw - py1
                new_py0 = px0
                new_px1 = rw - py0
                new_py1 = px1
            transformed.append(OcrWord(
                text=w.text,
                px0=new_px0, py0=new_py0,
                px1=new_px1, py1=new_py1,
                conf=w.conf,
            ))
        result = _merge_word_lists(result, transformed, tol=20)
    return result


def _ocr_crop(crop_img: Image.Image, assets_dir=None) -> list[OcrWord]:
    """
    OCR через Tesseract v5 (LSTM).
    Запускает несколько вариантов препроцессинга (grayscale + min-channel)
    и режимов PSM (11=sparse, 6=block), объединяет результаты.
    Возвращает слова с координатами в ИСХОДНЫХ пикселях кропа.
    """
    if _HAS_OCR_CACHE and assets_dir:
        cached = _load_ocr_cache(crop_img, 'v1', assets_dir)
        if cached is not None:
            return cached
    variants = _make_gray_variants(crop_img)
    all_words: list[OcrWord] = []

    # PSM 6 (uniform block) — приоритетно для плотных текстовых сеток (таблицы, штамп-блоки)
    if _has_dense_text_grid(crop_img):
        dense_words = _run_tesseract(variants[0][0], psm=6, up_scale=variants[0][1])
        all_words = _merge_word_lists(all_words, dense_words, tol=8)

    # PSM 11 (sparse text) — для разбросанных аннотаций на чертежах
    # PSM 6 (uniform block) добавляем только для первого варианта (grayscale) —
    # подхватывает сплошные блоки текста в таблицах
    # Вариант 3 (equalize) — только PSM 11, без PSM 6 чтобы не удвоить шум
    for vi, (img_variant, up_scale) in enumerate(variants):
        batch11 = _run_tesseract(img_variant, psm=11, up_scale=up_scale)
        all_words = _merge_word_lists(all_words, batch11, tol=12)
        if vi == 0:
            # PSM 6 на grayscale варианте — дополнительно для табличного текста
            batch6 = _run_tesseract(img_variant, psm=6, up_scale=up_scale)
            # tol=15: PSM 6 bbox может чуть смещаться vs PSM 11 — дедуплицируем
            all_words = _merge_word_lists(all_words, batch6, tol=15)

    # PSM 7 (single text line) — для изолированных числовых значений на чистом фоне
    # (слайды 8, 18). Принимаем только слова-измерения/_TECH_MARKER чтобы не добавлять шум.
    batch7 = _run_tesseract(variants[0][0], psm=7, up_scale=variants[0][1])
    batch7_filtered = [
        w for w in batch7
        if _MEASUREMENT.match(w.text.strip()) or _TECH_MARKER.match(w.text.strip())
    ]
    all_words = _merge_word_lists(all_words, batch7_filtered, tol=10)

    up_scale_main = variants[0][1] if variants else 2.0
    rotated_words = _try_rotated_ocr(crop_img, up_scale_main)
    all_words = _merge_word_lists(all_words, rotated_words, tol=20)

    # 4x upscale re-OCR для маленьких низкоуверенных регионов (char height < 20px, conf < 0.60)
    small_regions = _find_small_regions(all_words)
    iw, ih = crop_img.size
    for rx0, ry0, rx1, ry1 in small_regions:
        rx0 = max(0, rx0); ry0 = max(0, ry0); rx1 = min(iw, rx1); ry1 = min(ih, ry1)
        if rx1 <= rx0 or ry1 <= ry0:
            continue
        sub = crop_img.crop((rx0, ry0, rx1, ry1))
        from PIL import ImageEnhance as _IE
        sub4x = sub.resize((sub.width * 4, sub.height * 4), Image.LANCZOS).convert("RGB")
        sub4x_enhanced = _IE.Contrast(sub4x.convert("L")).enhance(2.5).convert("RGB")
        sub_words_raw = _run_tesseract(sub4x_enhanced, psm=11, up_scale=4.0)
        # Конвертируем координаты из sub4x-пространства обратно в пространство кропа
        sub_words = [
            OcrWord(w.text, rx0 + w.px0, ry0 + w.py0, rx0 + w.px1, ry0 + w.py1, w.conf)
            for w in sub_words_raw
        ]
        all_words = _merge_word_lists(all_words, sub_words, tol=6)

    if _HAS_OCR_CACHE and assets_dir:
        _save_ocr_cache(crop_img, 'v1', all_words, assets_dir)
    return all_words


# ── Шрифт ────────────────────────────────────────────────────────────────────

def _word_font(name: str | None) -> str:
    if not name:
        return "Times New Roman"
    clean = name.split("+")[-1]
    for suffix in ["-Bold", "-Italic", "-BoldItalic", ",Bold", ",Italic"]:
        clean = clean.replace(suffix, "")
    _MAP = {
        "TimesNewRoman": "Times New Roman",
        "ArialMT":       "Arial",
        "Arial-BoldMT":  "Arial",
    }
    return _MAP.get(clean.strip(), "Times New Roman")


def _rgb_from_fitz(color_int) -> RGBColor:
    if color_int is None:
        return RGBColor(0, 0, 0)
    if isinstance(color_int, float):
        v = int(color_int * 255)
        return RGBColor(v, v, v)
    if isinstance(color_int, (list, tuple)):
        if len(color_int) == 3:
            r, g, b = color_int
            return RGBColor(int(r*255), int(g*255), int(b*255))
        return RGBColor(0, 0, 0)
    r = (color_int >> 16) & 0xFF
    g = (color_int >>  8) & 0xFF
    b =  color_int        & 0xFF
    return RGBColor(r, g, b)


# ── Text box helpers ──────────────────────────────────────────────────────────

def _set_no_line(txBox) -> None:
    from lxml import etree
    ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    spPr = txBox._element.find(f".//{{{ns}}}spPr")
    if spPr is None:
        return
    ln = spPr.find(f"{{{ns}}}ln")
    if ln is None:
        ln = etree.SubElement(spPr, f"{{{ns}}}ln")
    if ln.find(f"{{{ns}}}noFill") is None:
        etree.SubElement(ln, f"{{{ns}}}noFill")


def _set_no_fill(txBox) -> None:
    """Убираем заливку фона text box (прозрачный)."""
    from lxml import etree
    ns_a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    spPr = txBox._element.find(f".//{{{ns_a}}}spPr")
    if spPr is None:
        return
    # Ищем или создаём noFill в spPr
    if spPr.find(f"{{{ns_a}}}noFill") is None:
        # Убираем solidFill если есть
        sf = spPr.find(f"{{{ns_a}}}solidFill")
        if sf is not None:
            spPr.remove(sf)
        etree.SubElement(spPr, f"{{{ns_a}}}noFill")


def _group_lines_by_visual_row(lines: list[dict]) -> list[list[dict]]:
    if not lines:
        return []
    rows: list[list[dict]] = []
    cur_row = [lines[0]]
    cur_y0 = lines[0]["bbox"][1]
    line_h = lines[0]["bbox"][3] - lines[0]["bbox"][1]
    threshold = max(4.0, line_h * 0.6)
    for line in lines[1:]:
        y0 = line["bbox"][1]
        if abs(y0 - cur_y0) <= threshold:
            cur_row.append(line)
        else:
            rows.append(cur_row)
            cur_row = [line]
            cur_y0 = y0
    rows.append(cur_row)
    return rows


def _add_block_textbox(slide, block: dict) -> None:
    bx0, by0, bx1, by1 = block["bbox"]
    w_pt = max(bx1 - bx0, 4.0)
    h_pt = max(by1 - by0, 4.0)
    txBox = slide.shapes.add_textbox(
        Emu(_emu(bx0)), Emu(_emu(by0)),
        Emu(_emu(w_pt)), Emu(_emu(h_pt * 1.15)),
    )
    tf = txBox.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    _set_no_line(txBox)
    visual_rows = _group_lines_by_visual_row(block.get("lines", []))
    for ri, row_lines in enumerate(visual_rows):
        p = tf.paragraphs[0] if ri == 0 else tf.add_paragraph()
        for line in sorted(row_lines, key=lambda l: l["bbox"][0]):
            for span in line.get("spans", []):
                txt = span.get("text", "")
                if not txt:
                    continue
                run = p.add_run()
                run.text = txt
                fnt = run.font
                size_pt = span.get("size", 11.0) or 11.0
                fnt.size   = Pt(max(4, size_pt))
                fnt.name   = _word_font(span.get("font"))
                fnt.bold   = bool(span.get("flags", 0) & (1 << 4))
                fnt.italic = bool(span.get("flags", 0) & (1 << 1))
                fnt.color.rgb = _rgb_from_fitz(span.get("color"))


def _merge_close_lines(lines: list[list[OcrWord]], img_native_w: int) -> list[list[OcrWord]]:
    """Merges vertically close OCR lines into single multi-line groups.
    Улучшает поиск и логическую группировку аннотаций типа «СТАЛЬ / 45 / ГОСТ 1050».
    """
    from statistics import mean as _mean

    def _avg_y(ln: list[OcrWord]) -> float:
        return sum((w.py0 + w.py1) / 2 for w in ln) / len(ln)

    def _avg_h_words(a: list[OcrWord], b: list[OcrWord]) -> float:
        all_h = [w.py1 - w.py0 for w in a + b if w.py1 - w.py0 > 0]
        return _mean(all_h) if all_h else 1.0

    def _x_range(ln: list[OcrWord]) -> tuple[int, int]:
        return (min(w.px0 for w in ln), max(w.px1 for w in ln))

    for _pass in range(3):
        merged = False
        new_lines: list[list[OcrWord]] = []
        i = 0
        while i < len(lines):
            if i + 1 < len(lines):
                a = lines[i]
                b = lines[i + 1]
                # Only merge when b is strictly below a
                if _avg_y(b) > _avg_y(a):
                    avg_h = _avg_h_words(a, b)
                    gap = min(w.py0 for w in b) - max(w.py1 for w in a)
                    ax0, ax1 = _x_range(a)
                    bx0, bx1 = _x_range(b)
                    overlap = max(0, min(ax1, bx1) - max(ax0, bx0))
                    min_span = max(1, min(ax1 - ax0, bx1 - bx0))
                    overlap_frac = overlap / min_span
                    combined_w = max(ax1, bx1) - min(ax0, bx0)
                    width_ok = (img_native_w <= 0) or (combined_w < img_native_w * 0.75)
                    if gap < avg_h * 1.8 and overlap_frac > 0.25 and width_ok:
                        combined = sorted(a + b, key=lambda w: (w.py0, w.px0))
                        new_lines.append(combined)
                        i += 2
                        merged = True
                        continue
            new_lines.append(lines[i])
            i += 1
        lines = new_lines
        if not merged:
            break
    return lines


def _group_ocr_into_lines(words: list[OcrWord],
                          img_native_w: int = 0) -> list[list[OcrWord]]:
    """Группирует OCR-слова с близкими y-координатами в визуальные строки.
    Использует порог 40% высоты строки (не 70%) чтобы не сливать аннотации
    на разных уровнях чертежа. Удаляет строки шириной > 60% изображения.
    """
    if not words:
        return []
    # Сортируем по центру y, а не по py0 — стабильнее при разных baseline
    sorted_w = sorted(words, key=lambda w: (w.py0 + w.py1) / 2)
    lines: list[list[OcrWord]] = []
    cur_line = [sorted_w[0]]
    cur_cy = (sorted_w[0].py0 + sorted_w[0].py1) / 2
    avg_h = max(sorted_w[0].py1 - sorted_w[0].py0, 1)
    for w in sorted_w[1:]:
        h = max(w.py1 - w.py0, 1)
        cy = (w.py0 + w.py1) / 2
        # Порог: 50% средней высоты строки — слова на одной строке укладываются
        threshold = max(4, avg_h * 0.50)
        if abs(cy - cur_cy) <= threshold:
            cur_line.append(w)
            # Обновляем центр строки как среднее всех слов
            cur_cy = sum((ww.py0 + ww.py1) / 2 for ww in cur_line) / len(cur_line)
            avg_h = (avg_h + h) / 2
        else:
            lines.append(sorted(cur_line, key=lambda ww: ww.px0))
            cur_line = [w]
            cur_cy = cy
            avg_h = h
    lines.append(sorted(cur_line, key=lambda ww: ww.px0))

    # Фильтруем строки шире 80% изображения (без PSM 6 таких быть не должно)
    if img_native_w > 0:
        max_line_w = img_native_w * 0.80
        lines = [
            ln for ln in lines
            if (max(w.px1 for w in ln) - min(w.px0 for w in ln)) <= max_line_w
        ]

    # Фильтруем "штриховочные" строки: >70% слов ≤3 символа И средний conf < 0.55
    _CAPS_NOISE_PAT = _re.compile(r'^[A-Z]{2,4}[!;.,]?$')

    def _is_hatch_line(ln: list[OcrWord]) -> bool:
        short = sum(1 for w in ln if len(w.text.strip()) <= 3)
        avg_conf = sum(w.conf for w in ln) / len(ln)
        return (short / len(ln)) > 0.70 and avg_conf < 0.55

    def _is_caps_noise_line(ln: list[OcrWord]) -> bool:
        """Строки где >55% слов — 2-4 char ALL CAPS Latin без цифр и кириллицы."""
        caps_noise = sum(
            1 for w in ln
            if _CAPS_NOISE_PAT.match(w.text.strip())
            and not _CYRILLIC.search(w.text)
            and not _re.search(r"\d", w.text)
        )
        avg_conf = sum(w.conf for w in ln) / len(ln)
        return (caps_noise / len(ln)) > 0.55 and avg_conf < 0.65

    lines = [ln for ln in lines if not _is_hatch_line(ln) and not _is_caps_noise_line(ln)]

    # Разбиваем "широкие" строки по горизонтальным разрывам.
    # Если расстояние между соседними словами > 4× средней ширины слова,
    # это скорее всего две разные аннотации на одной y-высоте.
    split_lines: list[list[OcrWord]] = []
    for ln in lines:
        if len(ln) <= 1:
            split_lines.append(ln)
            continue
        avg_w = sum(w.px1 - w.px0 for w in ln) / len(ln)
        gap_thresh = max(avg_w * 4, 60)
        cur = [ln[0]]
        for w in ln[1:]:
            gap = w.px0 - cur[-1].px1
            if gap > gap_thresh:
                split_lines.append(cur)
                cur = [w]
            else:
                cur.append(w)
        split_lines.append(cur)
    lines = split_lines

    # Merge-back step: if two consecutive gap-split lines have the same
    # approximate y-center (within 1 line-height) and their combined width
    # still fits within 80% of image width, they are likely one annotation
    # that was falsely split.
    merged: list[list[OcrWord]] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            # Average y-centers
            cy1 = sum((w.py0 + w.py1) / 2 for w in ln) / len(ln)
            cy2 = sum((w.py0 + w.py1) / 2 for w in nxt) / len(nxt)
            avg_h_ln = sum(w.py1 - w.py0 for w in ln) / len(ln)
            avg_h_nxt = sum(w.py1 - w.py0 for w in nxt) / len(nxt)
            line_h = (avg_h_ln + avg_h_nxt) / 2
            # Combined bounding box width
            all_words = ln + nxt
            combined_w = max(w.px1 for w in all_words) - min(w.px0 for w in all_words)
            width_ok = (img_native_w <= 0) or (combined_w <= img_native_w * 0.80)
            if abs(cy1 - cy2) <= line_h and width_ok:
                merged.append(sorted(all_words, key=lambda ww: ww.px0))
                i += 2
                continue
        merged.append(ln)
        i += 1
    lines = merged

    return lines


_MEAS_TRAIL   = _re.compile(r'^([—\-±=]?\d+[.,]\d+)[a-zA-Z!°]+$')
_LEAD_NOISE   = _re.compile(r'^[\\~#*°]([=\-+]?\d)')
_BRACKET_DIG  = _re.compile(r'^\[(\d)')
_EQ_LETTER    = _re.compile(r'^=[a-zA-Z]$')
# Trailing comma/period from measurement values: -0.300, → -0.300, -0,88. → -0,88
_MEAS_TRAIL_PUNCT = _re.compile(r'^([—\-±=]?\d+[.,]\d+)[.,]+$')
# Trailing punct from digit-only tokens: 10300! → 10300
_DIGIT_TRAIL  = _re.compile(r'^(\d[\d.,]*)[\s!;.°]+$')
# 2-3 символьные ALL CAPS Latin без цифр/кириллицы — штриховочный шум
_CAPS2        = _re.compile(r'^[A-Z]{2,3}[!;.,]?$')
_INIT_CAP_NOISE = _re.compile(r'^[A-Z][a-z]{1,3}$')


def _clean_token(t: str) -> str:
    """Очищает OCR-токен от мусорных prefix/suffix: trailing буква, leading \\~*°[ перед числом."""
    # trailing single letter/symbol after decimal: -0.07g → -0.07
    m = _MEAS_TRAIL.match(t)
    if m:
        return m.group(1)
    # leading noise char before digit: \=0.36 → =0.36, ~0.30 → 0.30, *0.20 → 0.20, °0.07q → 0.07q
    if _LEAD_NOISE.match(t):
        t2 = t[1:]
        # second pass: handle compound cases (°0.07q → 0.07q → 0.07)
        m2 = _MEAS_TRAIL.match(t2)
        if m2:
            return m2.group(1)
        return t2
    if _BRACKET_DIG.match(t):
        return t[1:]
    # trailing comma/period from measurement values: -0.300, → -0.300
    m = _MEAS_TRAIL_PUNCT.match(t)
    if m:
        return m.group(1)
    # trailing punct from digit tokens: 10300! → 10300
    m = _DIGIT_TRAIL.match(t)
    if m:
        return m.group(1)
    return t


def _overlaps_native(
    ocr_bbox_pt: tuple[float, float, float, float],
    native_bboxes_pt: list[tuple[float, float, float, float]],
    tol: float = 5.0,
) -> bool:
    """Return True if the OCR line center falls inside any native text bbox (expanded by tol pt)."""
    cx = (ocr_bbox_pt[0] + ocr_bbox_pt[2]) / 2
    cy = (ocr_bbox_pt[1] + ocr_bbox_pt[3]) / 2
    for x0, y0, x1, y1 in native_bboxes_pt:
        if (x0 - tol) <= cx <= (x1 + tol) and (y0 - tol) <= cy <= (y1 + tol):
            return True
    return False


def _add_ocr_line_textbox(
    slide,
    line_words: list[OcrWord],
    img_pt_x: float,
    img_pt_y: float,
    img_pt_w: float,
    img_pt_h: float,
    crop_px_w: int,
    crop_px_h: int,
) -> None:
    """Добавляет один textbox для строки OCR-слов (объединённых по y-координате)."""
    if crop_px_w <= 0 or crop_px_h <= 0 or not line_words:
        return
    sx = img_pt_w / crop_px_w
    sy = img_pt_h / crop_px_h

    px0 = min(w.px0 for w in line_words)
    py0 = min(w.py0 for w in line_words)
    px1 = max(w.px1 for w in line_words)
    py1 = max(w.py1 for w in line_words)

    x_pt = img_pt_x + px0 * sx
    y_pt = img_pt_y + py0 * sy
    w_pt = max((px1 - px0) * sx * 1.10, 4.0)
    h_pt = max((py1 - py0) * sy * 1.4, 4.0)
    # Шрифт: 25-й перцентиль высот слов (консервативнее медианы, избегает инфляции от подстрочников)
    word_heights = sorted((w.py1 - w.py0) for w in line_words)
    p25_h = word_heights[len(word_heights) // 4]
    # Динамический cap: 14.0 для высококонфидентных строк, иначе 11.0
    all_high_conf = all(w.conf > 0.70 for w in line_words)
    font_cap = 14.0 if all_high_conf else 11.0
    font_size = min(font_cap, max(5.0, p25_h * sy * 0.72))

    txBox = slide.shapes.add_textbox(
        Emu(_emu(x_pt)), Emu(_emu(y_pt)),
        Emu(_emu(w_pt)), Emu(_emu(h_pt)),
    )
    tf = txBox.text_frame
    tf.word_wrap = False
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    _set_no_line(txBox)
    _set_no_fill(txBox)

    p = tf.paragraphs[0]
    run = p.add_run()
    # Inline-фильтры шумовых токенов
    _inline_noise   = _re.compile(r'^["\'\`\*\\\|\^~<>{}\[\]@#!]+$|^["\'\`\*][a-z]{1,3}$')
    _inline_low_lat = _re.compile(r'^[a-z]{1,5}[).,!|]*$')

    def _keep_word(w: OcrWord) -> tuple[bool, str]:
        t = w.text.strip()
        # Пунктуационный или цитатный мусор
        if _inline_noise.match(t):
            return False, t
        # Строчный латинский без цифр/кириллицы
        if _inline_low_lat.match(t) and not _CYRILLIC.search(t) and not _re.search(r"\d", t):
            return False, t
        # ≥3-символьные ALL CAPS Latin без кириллицы (уже не проходят _is_valid_ocr)
        if _ALL_CAPS_LATIN.match(t) and not _CYRILLIC.search(t):
            return False, t
        # 2-3-символьные ALL CAPS Latin — штриховочный шум (SS, CA, LN, FS, Ne→No)
        if _CAPS2.match(t) and not _CYRILLIC.search(t) and not _re.search(r"\d", t):
            return False, t
        # Начальная заглавная + 1-3 строчные Latin без цифр/кириллицы — штриховочный шум (Ne, Kr, Go, Gy, Ren)
        if _INIT_CAP_NOISE.match(t) and not _CYRILLIC.search(t) and not _re.search(r"\d", t) and w.conf < 0.75:
            return False, t
        # = + одна буква: =f, =g — шум
        if _EQ_LETTER.match(t):
            return False, t
        # Очищаем токен: trailing буква после числа, leading \~[ перед числом
        cleaned = _clean_token(t)
        if _DASH_SEQ.match(cleaned) and not _CYRILLIC.search(cleaned):
            return False, cleaned
        return True, cleaned

    cleaned_parts: list[str] = []
    for w in line_words:
        keep, cleaned = _keep_word(w)
        if keep and cleaned:
            cleaned_parts.append(cleaned)

    if not cleaned_parts:
        cleaned_parts = [w.text for w in line_words]
    run.text = " ".join(cleaned_parts)
    run.font.size  = Pt(font_size)
    run.font.name  = "Times New Roman"
    run.font.color.rgb = RGBColor(0, 0, 0)


# ── Фон слайда ───────────────────────────────────────────────────────────────

def _set_slide_bg(slide, rgb: tuple[int, int, int]) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(*rgb)


def _has_vector_content(
    span_rects: list[tuple], img_rects: list[tuple], pw: float, ph: float
) -> bool:
    text_area = sum((x1-x0)*(y1-y0) for x0,y0,x1,y1 in span_rects)
    img_area  = sum((x1-x0)*(y1-y0) for x0,y0,x1,y1 in img_rects)
    covered   = (text_area + img_area) / (pw * ph) if pw * ph > 0 else 0
    return covered < 0.95


# ── Главная функция ───────────────────────────────────────────────────────────

def emit_pptx_slides(
    ir,
    output_path: Path,
    pdf_path: Path,
    *,
    dpi: int = 200,
    assets_dir: Path | None = None,
    ocr_images: bool = True,
) -> Path:
    """
    Конвертирует slide-PDF в PPTX.
    Каждый слайд: белый фон + вектор-слой + отдельные изображения (с OCR) + text boxes.
    """
    work_dir = assets_dir or output_path.parent / "pptx_assets"
    raw_dir  = work_dir / "raw"
    vec_dir  = work_dir / "vector"
    img_dir  = work_dir / "images"
    msk_dir  = work_dir / "img_masked"
    for d in (raw_dir, vec_dir, img_dir, msk_dir):
        d.mkdir(parents=True, exist_ok=True)

    scale = dpi / 72.0
    mat   = fitz.Matrix(scale, scale)

    pdf_doc   = fitz.open(pdf_path)
    page_data = []

    for i in range(pdf_doc.page_count):
        fz_page = pdf_doc.load_page(i)
        rect    = fz_page.rect
        pw, ph  = rect.width, rect.height

        # ── 1. Рендер страницы ────────────────────────────────────────────
        pix     = fz_page.get_pixmap(matrix=mat, alpha=False)
        raw_png = raw_dir / f"slide_{i:03d}.png"
        pix.save(str(raw_png))
        img_full = Image.open(raw_png).convert("RGB")
        iw, ih   = img_full.size

        # ── 2. Текстовые блоки (native PDF text) ──────────────────────────
        text_dict   = fz_page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        text_blocks = [b for b in text_dict.get("blocks", []) if b.get("type") == 0]

        span_rects: list[tuple] = []
        for block in text_blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip():
                        span_rects.append(tuple(span["bbox"]))

        # ── 3. Изображения (get_image_info с xrefs) ───────────────────────
        img_infos = fz_page.get_image_info(xrefs=True)
        img_rects: list[tuple] = [
            tuple(info["bbox"]) for info in img_infos
            if info.get("bbox") and (info["bbox"][2]-info["bbox"][0]) > 4
        ]

        # ── 4. Кропы + OCR для каждого изображения ────────────────────────
        cropped_data: list[dict] = []
        for bi, info in enumerate(img_infos):
            bx0, by0, bx1, by1 = info["bbox"]
            pw_img = bx1 - bx0
            ph_img = by1 - by0
            if pw_img < 4 or ph_img < 4:
                continue

            # Пиксельные координаты кропа в рендере (для отображения/маскировки)
            cpx0 = max(0, int(bx0 * scale))
            cpy0 = max(0, int(by0 * scale))
            cpx1 = min(iw, int(bx1 * scale))
            cpy1 = min(ih, int(by1 * scale))
            if cpx1 - cpx0 < 4 or cpy1 - cpy0 < 4:
                continue

            raw_crop = img_full.crop((cpx0, cpy0, cpx1, cpy1))
            crop_w, crop_h = raw_crop.size

            # Пробуем нативное извлечение изображения (выше разрешение → лучше OCR)
            xref = info.get("xref", 0)
            native_img: Image.Image | None = None
            if xref:
                try:
                    import io as _io
                    img_data = pdf_doc.extract_image(xref)
                    raw_bytes = img_data.get("image")
                    if raw_bytes:
                        native_img = Image.open(_io.BytesIO(raw_bytes)).convert("RGB")
                except Exception:
                    native_img = None

            ocr_source = native_img if native_img else raw_crop
            native_w, native_h = ocr_source.size

            # OCR
            ocr_words: list[OcrWord] = []
            # Пропускаем маленькие декоративные изображения (логотипы, иконки)
            # Реальные чертежи всегда >= 900px по обоим измерениям
            _is_tiny = min(native_w, native_h) < 600
            if ocr_images and native_w > 30 and native_h > 20 and not _is_tiny:
                print(f"  Слайд {i}, image {bi}: OCR ({native_w}x{native_h}px, "
                      f"{'native' if native_img else 'rendered'})...")
                ocr_words = _ocr_crop(ocr_source)
                print(f"    → {len(ocr_words)} слов")

            # Если OCR делался на нативном изображении, масштабируем координаты
            # в пиксели рендер-кропа (для маскировки)
            if native_img and ocr_words:
                sx = crop_w / native_w
                sy = crop_h / native_h
                render_words = [
                    OcrWord(w.text,
                            int(w.px0 * sx), int(w.py0 * sy),
                            int(w.px1 * sx), int(w.py1 * sy),
                            w.conf)
                    for w in ocr_words
                ]
            else:
                render_words = ocr_words

            # Замазываем OCR-области в кропе (убираем текст из растра)
            masked_crop = raw_crop
            if render_words:
                ocr_rects_px = [(w.px0, w.py0, w.px1, w.py1) for w in render_words]
                masked_crop = _mask_rects(raw_crop, ocr_rects_px, pad=3)

            masked_path = msk_dir / f"slide_{i:03d}_img_{bi}.png"
            masked_crop.save(str(masked_path))

            # OCR-слова хранятся в нативных координатах (для точного позиционирования)
            cropped_data.append({
                "path":      masked_path,
                "bbox_pt":   (bx0, by0, bx1, by1),
                "crop_px":   (native_w, native_h),  # нативный размер для масштабирования
                "words":   ocr_words,
            })

        # ── 5. Вектор-слой (без текста и без image-blocks) ────────────────
        bg_color = _page_bg_color(img_full)
        vec_img  = _mask_rects(
            img_full,
            _pt_rects_to_px(span_rects, scale),
        )
        vec_img  = _mask_rects(
            vec_img,
            _pt_rects_to_px(img_rects, scale),
            fill=bg_color,
        )

        has_vec = _has_vector_content(span_rects, img_rects, pw, ph)
        vec_png: Path | None = None
        if has_vec:
            vec_png = vec_dir / f"slide_{i:03d}_vec.png"
            vec_img.save(str(vec_png))

        page_data.append((bg_color, vec_png, cropped_data, text_blocks, pw, ph))
        print(f"  Слайд {i}: {len(img_infos)} imgs ({sum(len(c['words']) for c in cropped_data)} OCR-слов), {len(text_blocks)} text blocks")

    pdf_doc.close()

    # ── 6. Сборка PPTX ───────────────────────────────────────────────────────
    prs = Presentation()

    for i, (bg_color, vec_png, cropped_data, text_blocks, pw, ph) in enumerate(page_data):
        prs.slide_width  = Emu(_emu(pw))
        prs.slide_height = Emu(_emu(ph))
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        _set_slide_bg(slide, bg_color)

        # Вектор-слой (декор, рамки, линии)
        if vec_png:
            slide.shapes.add_picture(
                str(vec_png), Emu(0), Emu(0), Emu(_emu(pw)), Emu(_emu(ph)),
            )

        # Изображения (замазанные кропы) на своих позициях
        for cd in cropped_data:
            bx0, by0, bx1, by1 = cd["bbox_pt"]
            slide.shapes.add_picture(
                str(cd["path"]),
                Emu(_emu(bx0)), Emu(_emu(by0)),
                Emu(_emu(bx1 - bx0)), Emu(_emu(by1 - by0)),
            )

        # Collect native text block bboxes for dedup check
        native_bboxes_pt = [tuple(block["bbox"]) for block in text_blocks]

        # OCR text boxes поверх каждого изображения (группировка по строкам)
        for cd in cropped_data:
            bx0, by0, bx1, by1 = cd["bbox_pt"]
            cw, ch = cd["crop_px"]
            sx = (bx1 - bx0) / cw if cw > 0 else 1.0
            sy = (by1 - by0) / ch if ch > 0 else 1.0
            lines = _group_ocr_into_lines(cd["words"], img_native_w=cw)
            lines = _merge_close_lines(lines, cw)
            for line_words in lines:
                if not line_words:
                    continue
                px0 = min(w.px0 for w in line_words)
                py0 = min(w.py0 for w in line_words)
                px1 = max(w.px1 for w in line_words)
                py1 = max(w.py1 for w in line_words)
                ocr_bbox_pt = (
                    bx0 + px0 * sx,
                    by0 + py0 * sy,
                    bx0 + px1 * sx,
                    by0 + py1 * sy,
                )
                if _overlaps_native(ocr_bbox_pt, native_bboxes_pt):
                    continue
                _add_ocr_line_textbox(
                    slide, line_words,
                    img_pt_x=bx0, img_pt_y=by0,
                    img_pt_w=bx1-bx0, img_pt_h=by1-by0,
                    crop_px_w=cw, crop_px_h=ch,
                )

        # Native PDF text boxes
        for block in text_blocks:
            _add_block_textbox(slide, block)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    return output_path


def _pt_rects_to_px(
    rects_pt: list[tuple], scale: float
) -> list[tuple[int, int, int, int]]:
    return [
        (int(x0*scale), int(y0*scale), int(x1*scale), int(y1*scale))
        for x0, y0, x1, y1 in rects_pt
    ]

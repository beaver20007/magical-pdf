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
# Полностью заглавные латинские слова >=4 букв — OCR мусор (ALLY, NALLY, WHICH)
# Сохраняем: 3-буквенные (MBX, ALY - риск, но они редки); 2-буквенные (PP, DN - OK)
_ALL_CAPS_LATIN  = _re.compile(r"^[A-Z]{4,}$")


def _is_valid_ocr(text: str) -> bool:
    """
    Принимаем OCR-результат если:
    - длина >= 1 (одиночный маркер типа B, C, А)
    - содержит хотя бы 1 кириллическую/латинскую букву или цифру
    - не является пунктуационным мусором или штриховочным шумом
    - ≥ 40% символов — "чистые"
    """
    t = text.strip()
    if not t:
        return False
    # Одиночный символ — только размерный маркер (заглавная буква или цифра)
    if len(t) == 1:
        return bool(_re.match(r"[А-ЯA-Z0-9]", t))
    if not _ALPHANUM.search(t):
        return False
    if _NOISE.match(t):
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
    if len(t) == 1:
        return 80   # одиночные символы — только при высокой уверенности
    if _MEASUREMENT.match(t):
        return 20   # числа-измерения — очень низкий порог, сложный фон на чертежах
    if _TECH_MARKER.match(t):
        return 20   # технические маркеры: i=4%, 1:200, уклон
    if _re.match(r"^\d{1,4}$", t):
        return 25   # целые числа (размеры, диаметры) — чуть выше порог от мусора
    if len(t) <= 2:
        return 50   # короткие аббревиатуры
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
        txt = (data["text"][j] or "").strip()
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


def _ocr_crop(crop_img: Image.Image) -> list[OcrWord]:
    """
    OCR через Tesseract v5 (LSTM).
    Запускает несколько вариантов препроцессинга (grayscale + min-channel)
    и режимов PSM (11=sparse, 6=block), объединяет результаты.
    Возвращает слова с координатами в ИСХОДНЫХ пикселях кропа.
    """
    variants = _make_gray_variants(crop_img)
    all_words: list[OcrWord] = []

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
    def _is_hatch_line(ln: list[OcrWord]) -> bool:
        short = sum(1 for w in ln if len(w.text.strip()) <= 3)
        avg_conf = sum(w.conf for w in ln) / len(ln)
        return (short / len(ln)) > 0.70 and avg_conf < 0.55

    lines = [ln for ln in lines if not _is_hatch_line(ln)]

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

    return lines


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
    # Шрифт: медиана высот слов (стабильнее чем span всей строки)
    word_heights = sorted((w.py1 - w.py0) for w in line_words)
    med_h = word_heights[len(word_heights) // 2]
    font_size = min(11.0, max(5.0, med_h * sy * 0.72))

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
    # Внутри строки убираем шумовые токены: пунктуация и строчный латинский мусор
    # Чистая пунктуация или слова начинающиеся с кавычки+"ts" стиля шума
    _inline_noise   = _re.compile(r'^["\'\`\*\\\|\^~<>{}\[\]@#!]+$|^["\'\`\*][a-z]{1,3}$')
    _inline_low_lat = _re.compile(r'^[a-z]{1,5}[).,!|]*$')
    clean_words = [
        w for w in line_words
        if not _inline_noise.match(w.text.strip())
        and not (_inline_low_lat.match(w.text.strip())
                 and not _CYRILLIC.search(w.text)
                 and not _re.search(r"\d", w.text))
        and not (_ALL_CAPS_LATIN.match(w.text.strip())
                 and not _CYRILLIC.search(w.text))
    ]
    if not clean_words:
        clean_words = line_words
    run.text = " ".join(w.text for w in clean_words)
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

        # OCR text boxes поверх каждого изображения (группировка по строкам)
        for cd in cropped_data:
            bx0, by0, bx1, by1 = cd["bbox_pt"]
            cw, ch = cd["crop_px"]
            for line_words in _group_ocr_into_lines(cd["words"], img_native_w=cw):
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

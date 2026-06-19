"""
add_pdf_text_layer.py — Phase 48: добавляет невидимый OCR-текстовый слой в PDF.

Делает оригинальный PDF полнотекстовым/поисковым в любом PDF-ридере,
не требуя PPTX. Использует pymupdf (fitz) для вставки белого (невидимого)
текста поверх каждой страницы с изображениями.

CLI:
    python add_pdf_text_layer.py input.pdf [output.pdf]

Если output.pdf не указан, результат сохраняется как input_with_ocr.pdf
рядом с оригиналом.
"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz  # pymupdf

# Минимальный размер изображения для OCR (в пикселях) — такой же, как в основном пайплайне
_MIN_IMG_AREA_PX = 40_000   # ~200×200 px
_MIN_IMG_DIM_PT  = 30.0     # минимум 30pt по одной из сторон

# Импортируем OCR-функции из основного пайплайна
try:
    from src.pipeline.emit_pptx_slides import (
        _ocr_crop,
        _group_ocr_into_lines,
    )
    from PIL import Image
except ImportError as _e:
    print(f"[ERROR] Не удалось импортировать пайплайн: {_e}")
    print("  Запустите из корня проекта: python add_pdf_text_layer.py input.pdf")
    sys.exit(1)


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _pt(v: float) -> float:
    """Округляет координату в pt до 2 знаков."""
    return round(float(v), 2)


def _extract_large_images(page: fitz.Page):
    """
    Возвращает список (xref, rect_pt, pix) для «больших» растровых изображений
    на странице (аналог фильтрации в emit_pptx_slides).

    rect_pt  — fitz.Rect в pt (origin top-left)
    pix      — fitz.Pixmap изображения
    """
    large = []
    page_w = page.rect.width
    page_h = page.rect.height

    for img_info in page.get_image_info(xrefs=True):
        xref = img_info.get("xref", 0)
        if not xref:
            continue

        # Bbox изображения на странице (в pt)
        bbox = img_info.get("bbox")
        if not bbox:
            continue
        rect = fitz.Rect(bbox)
        w_pt = rect.width
        h_pt = rect.height

        # Фильтр: слишком маленькие — пропускаем
        if w_pt < _MIN_IMG_DIM_PT or h_pt < _MIN_IMG_DIM_PT:
            continue
        # Пропускаем изображения ≥ 95% страницы (фоновые текстуры)
        if w_pt >= page_w * 0.95 and h_pt >= page_h * 0.95:
            continue

        try:
            pix = fitz.Pixmap(page.parent, xref)
        except Exception:
            continue

        # Фильтр по площади в пикселях
        if pix.width * pix.height < _MIN_IMG_AREA_PX:
            pix = None
            continue

        # Конвертируем в RGB если нужно (убираем прозрачность / CMYK)
        if pix.n not in (3, 4):
            try:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            except Exception:
                pix = None
                continue
        if pix.alpha:
            try:
                pix = fitz.Pixmap(pix, 0)  # убираем альфа-канал
            except Exception:
                pix = None
                continue

        large.append((xref, rect, pix))

    return large


def _pix_to_pil(pix: fitz.Pixmap) -> Image.Image:
    """Конвертирует fitz.Pixmap в PIL.Image (RGB)."""
    import io
    buf = pix.tobytes("png")
    return Image.open(io.BytesIO(buf)).convert("RGB")


def _add_text_layer_to_page(page: fitz.Page, verbose: bool = False) -> int:
    """
    Добавляет невидимый текстовый слой для всех больших изображений на странице.
    Возвращает количество добавленных строк текста.
    """
    images = _extract_large_images(page)
    if not images:
        return 0

    total_lines = 0

    for xref, rect, pix in images:
        crop_img = _pix_to_pil(pix)
        crop_px_w, crop_px_h = crop_img.size

        if crop_px_w <= 0 or crop_px_h <= 0:
            continue

        # Масштаб: пиксель → pt
        sx = rect.width  / crop_px_w   # pt per pixel (x)
        sy = rect.height / crop_px_h   # pt per pixel (y)

        # Запускаем OCR
        words = _ocr_crop(crop_img)
        if not words:
            continue

        lines = _group_ocr_into_lines(words, img_native_w=crop_px_w)
        if not lines:
            continue

        for line_words in lines:
            if not line_words:
                continue

            # Бounding box строки в пикселях кропа
            px0 = min(w.px0 for w in line_words)
            py0 = min(w.py0 for w in line_words)
            px1 = max(w.px1 for w in line_words)
            py1 = max(w.py1 for w in line_words)

            # Центр строки в pt (координаты страницы, origin top-left)
            line_cx_pt = _pt(rect.x0 + (px0 + px1) / 2 * sx)
            line_cy_pt = _pt(rect.y0 + (py0 + py1) / 2 * sy)

            # Размер шрифта на основе высоты строки (в pt)
            line_h_pt = (py1 - py0) * sy
            if line_h_pt > 18:
                font_size = min(28.0, line_h_pt * 0.75)
            elif line_h_pt > 10:
                font_size = max(5.0, line_h_pt * 0.72)
            else:
                font_size = max(5.0, line_h_pt * 0.80)
            font_size = max(4.0, font_size)

            # Текст строки
            line_text = " ".join(w.text for w in line_words)

            # Вставляем невидимый текст (белый цвет = невидимый, но индексируемый)
            # render_mode=3 — только для поиска, не рисуется
            try:
                page.insert_text(
                    fitz.Point(line_cx_pt, line_cy_pt),
                    line_text,
                    fontsize=font_size,
                    color=(1, 1, 1),      # белый — невидимый на любом фоне
                    render_mode=3,        # invisible text (PDF Tr=3)
                    overlay=False,        # под содержимым страницы
                )
                total_lines += 1
                if verbose:
                    print(f"      [{line_cy_pt:.1f}pt] {line_text!r}")
            except Exception as exc:
                if verbose:
                    print(f"      [WARN] insert_text failed: {exc}")

    return total_lines


# ── Основная функция ──────────────────────────────────────────────────────────

def add_pdf_text_layer(
    input_path: str | Path,
    output_path: str | Path | None = None,
    verbose: bool = False,
) -> Path:
    """
    Открывает PDF, добавляет невидимый OCR-текстовый слой и сохраняет результат.

    Args:
        input_path:  путь к исходному PDF
        output_path: путь для сохранения; если None — <stem>_with_ocr.pdf рядом с исходным
        verbose:     выводить прогресс по строкам

    Returns:
        Path к итоговому PDF-файлу
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"PDF не найден: {input_path}")

    if output_path is None:
        output_path = input_path.with_name(input_path.stem + "_with_ocr.pdf")
    output_path = Path(output_path)

    print(f"[add_pdf_text_layer] Открываем: {input_path}")
    doc = fitz.open(str(input_path))
    total_pages = len(doc)

    grand_total = 0
    for page_idx in range(total_pages):
        page = doc[page_idx]
        print(f"  Страница {page_idx + 1}/{total_pages} ...", end=" ", flush=True)
        n = _add_text_layer_to_page(page, verbose=verbose)
        print(f"{n} строк")
        grand_total += n

    print(f"[add_pdf_text_layer] Итого добавлено строк: {grand_total}")
    print(f"[add_pdf_text_layer] Сохраняем: {output_path}")
    doc.save(str(output_path), garbage=4, deflate=True)
    doc.close()

    return output_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Использование: python add_pdf_text_layer.py input.pdf [output.pdf]")
        sys.exit(1)

    input_pdf  = sys.argv[1]
    output_pdf = sys.argv[2] if len(sys.argv) >= 3 else None

    result = add_pdf_text_layer(input_pdf, output_pdf, verbose="--verbose" in sys.argv)
    print(f"Готово: {result}")


if __name__ == "__main__":
    main()

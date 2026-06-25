# magical-pdf — Полный роадмап фич (v2, 2026-06)

**Основа:** `PDF_UTILITIES_ROADMAP.md` + 20 новых фич, согласованных с владельцем продукта 2026-06-25.

Цель: превратить magical-pdf в **лучший локальный PDF-хаб** — паритет с iLovePDF, Adobe Acrobat, плюс уникальные AI-фичи экосистемы DOCRAFT.

---

## Текущий статус

| Слой | Статус |
|------|--------|
| **Protect** (PDF → скан без текслоя) | ✅ Отгружен |
| **Extract** Phase 5.1 (OCR pipeline, ocr-docs) | ✅ Готов |
| **Extract** Phase 5.2–5.3 (UI, Jobs API) | 🔄 В работе (следующая задача) |

---

## Все 20 фич — индекс

| # | Фича | Группа | Сложность | Фаза |
|---|------|---------|-----------|------|
| 1 | Объединить PDF (Merge) | iLovePDF | Низкая | 6 |
| 2 | Разделить PDF (Split) | iLovePDF | Низкая | 6 |
| 3 | Сжать PDF (Compress) | iLovePDF | Низкая | 6 |
| 4 | Повернуть страницы (Rotate) | iLovePDF | Низкая | 6 |
| 5 | PDF → Word / PPTX / Excel | iLovePDF | Средняя | 7 |
| 6 | Изображения → PDF | iLovePDF | Низкая | 6 |
| 7 | Снять / установить пароль | iLovePDF | Низкая | 6 |
| 8 | Заполнить PDF-форму | Adobe | Средняя | 7 |
| 9 | Редактировать текст inline | Adobe | Высокая | 10 |
| 10 | Редактировать метаданные | Adobe | Низкая | 6 |
| 11 | Нумерация страниц | Adobe | Низкая | 6 |
| 12 | Сравнение двух PDF (Diff) | Adobe | Высокая | 9 |
| 13 | Редакция / Redact | Adobe | Средняя | 7 |
| 14 | AI Summary → карточка | Unique AI | Низкая | 8 |
| 15 | AI Smart Redact (авто-PII) | Unique AI | Средняя | 8 |
| 16 | AI Extract → JSON | Unique AI | Средняя | 8 |
| 17 | PDF Chat (Q&A) | Unique AI | Высокая | 10 |
| 18 | Capture-to-PDF pipeline (N11) | Unique AI | Средняя | 9 |
| 19 | PDF Linter (accessibility) | Unique AI | Средняя | 9 |
| 20 | Watermark брендовый | Unique AI | Низкая | 6 |

---

## Фазы разработки

### Phase 5.2–5.3 (текущая) — Extract UI + Jobs API
*Продолжение уже идущей работы*

- [ ] Extract tab UI (Tauri + web)
- [ ] Wire `/jobs` API → localhost:8765
- [ ] Прогресс-бар OCR → ready
- [ ] Скачать DOCX / PPTX результат

---

### Phase 5.4 — Tauri auto-spawn Extract server
- [ ] Tauri sidecar: `ocr-docs` сервер поднимается при старте приложения
- [ ] Health-check + reconnect логика

---

### Phase 6 — Базовый тулбокс (9 quick-wins)
*Инструменты: pdf-lib (WASM), pdf.js. Срок: ~3 недели.*

| # | Реализация |
|---|-----------|
| 1 | Merge: drag-n-drop порядок → `PDFDocument.copyPages()` |
| 2 | Split: диапазоны страниц → отдельные файлы |
| 3 | Compress: Ghostscript sidecar (desktop) / qpdf; 3 пресета |
| 4 | Rotate: per-page 90/180/270 → `page.setRotation()` |
| 6 | Images→PDF: JPG/PNG/TIFF → pdf-lib embed |
| 7 | Protect/Unlock: AES-256 encrypt / user-pwd remove (qpdf sidecar) |
| 10 | Metadata editor: Title, Author, Keywords, Subject, Created |
| 11 | Page numbers: overlay колонтитул; выбор шрифта/позиции/формата |
| 20 | Watermark: overlay текст или PNG; opacity, угол, диапазон страниц |

UI: единая вкладка **Инструменты** с плиточным меню операций.

---

### Phase 7 — Профессиональные инструменты (3 фичи)
*Зависимости: LibreOffice/unoconv sidecar (фича #5), pymupdf (фича #8).*

| # | Детали |
|---|--------|
| 5 | PDF→Word/PPTX/Excel через `libreoffice --headless --convert-to docx`; только для Tauri (sidecar) |
| 8 | AcroForm detect → поле-за-полем заполнение → flatten; pymupdf `Page.insert_text` |
| 13 | Redact: пользователь рисует прямоугольники → `Page.add_redact_annot()` → `apply_redactions()`; необратимо |

---

### Phase 8 — AI Quick Wins (3 фичи Claude API)
*Модель: claude-sonnet-4-6 с кэшированием. Требует сетевого соединения.*

| # | Prompt / архитектура |
|---|---------------------|
| 14 | AI Summary: `extract_text(pdf)` → Claude → 5 тезисов + 3 action items → карточка + скачать DOCX |
| 16 | AI Extract→JSON: загружаем PDF счёта/договора → Claude с JSON schema → скачать `.json` / Excel; поддержка: сумма, стороны, даты, реквизиты |
| 15 | AI Smart Redact: Claude/NER ищет PII (имена, email, ИНН, адреса) → подсвечивает предложения → пользователь выбирает → фаза 7 Redact |

UI: вкладка **AI** рядом с Protect/Extract/Инструменты.

---

### Phase 9 — Интеграции + Качество (3 фичи)
*Зависимость фичи #18 — N11 флаги Railway/Vercel должны быть включены.*

| # | Детали |
|---|--------|
| 12 | PDF Diff: две версии → difflib на тексте + визуальный pixel-diff по страницам → HTML-отчёт с подсветкой |
| 19 | PDF Linter: проверяет теги (`/StructTreeRoot`), alt-текст, язык, Title; отчёт с советами по WCAG; pymupdf metadata read |
| 18 | Capture-to-PDF: desktop-instructor capture-pack ZIP → POST `/generate/with-captures` → PDF с аннотациями; кнопка «Открыть в Magical» из N11 UI |

---

### Phase 10 — Тяжёлые / Премиум (2 фичи)
*Только для Docraft Pro плана.*

| # | Детали |
|---|--------|
| 9 | Inline text edit: pymupdf `Page.search_for()` + `Page.draw_rect()` + `Page.insert_text()`; сохраняет шрифт и размер; только Tauri (не web) |
| 17 | PDF Chat: embed страниц через Claude `document` content block → streaming Q&A в sidebar; RAG не нужен при < 100 стр |

---

## Технический стек по фазам

| Слой | Инструмент | Фазы |
|------|-----------|------|
| PDF манипуляции (JS/WASM) | pdf-lib | 6 |
| PDF низкий уровень (Python) | pymupdf (`fitz`) | 7, 8, 9, 10 |
| PDF утилиты (sidecar) | qpdf / Ghostscript | 6 (compress, unlock) |
| Конвертация (sidecar) | LibreOffice `--headless` | 7 |
| AI операции | claude-sonnet-4-6 | 8, 9, 10 |
| Рендер / предпросмотр | pdf.js | уже есть |

---

## Порядок реализации (по ценности / сложности)

```
5.2 → 5.3 → 5.4      Extract UI завершение (текущее)
   ↓
Phase 6               9 quick-wins (1 итерация, ~3 нед)
   ↓
Phase 8               3 AI фичи (Claude API, быстрые)
   ↓
Phase 7               3 средних инструмента (sidecar зависимости)
   ↓
Phase 9               интеграции и качество
   ↓
Phase 10              Премиум-фичи (позже)
```

> Phase 8 (AI) идёт до Phase 7 (sidecar) — AI-фичи не требуют LibreOffice/qpdf и дают быстрый wow-эффект.

---

## Docraft UI хуки (обновление)

| CTA в Docraft | magical-pdf deep link |
|---------------|----------------------|
| Защитить PDF | `?source=docraft&mode=protect` |
| PDF: инструменты | `?source=docraft&mode=tools` |
| Распознать в Word | `?source=docraft&mode=extract` |
| AI-анализ PDF | `?source=docraft&mode=ai` |
| Открыть из N11 | `?source=n11&mode=tools&file=<path>` |

---

*Этот файл заменяет и расширяет `PDF_UTILITIES_ROADMAP.md`. Старый файл сохранён как архив.*

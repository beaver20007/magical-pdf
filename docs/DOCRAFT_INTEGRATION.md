# Magical PDF в экосистеме DOCRAFT

Magical PDF — **локальный PDF-хаб** в DOCRAFT. Сегодня: слой **Protect** (PDF → скан без текстового слоя). План: **Utilities** (merge, compress, …) и **Extract** (скан → DOCX/PPTX, слияние с [ocr-docs](https://github.com/beaver20007/docraft)).

> Дорожная карта utilities: [`PDF_UTILITIES_ROADMAP.md`](./PDF_UTILITIES_ROADMAP.md).  
> План слияния Extract: ocr-docs `docs/ECOSYSTEM_ROADMAP.md`.

## Карта экосистемы

| Компонент | Роль | Где живёт |
|-----------|------|-----------|
| **Docraft** | Создание и экспорт учебных/рабочих PDF с **текстовым слоём** | Облако или локально (по продукту Docraft) |
| **Desktop Instructor** | Рабочее место автора: материалы, экспорт, сценарии обучения | Desktop / web-клиент DOCRAFT |
| **Magical PDF** | **Protect** + планируемые **Utilities** + **Extract** (единый UI) | Этот репозиторий |
| **ocr-docs** | Песочница **Extract** до слияния с magical-pdf | `C:\Projects\ocr-docs` |
| **DOCRAFT meta-repo** | Карта репозиториев, версии, процессы релиза | [github.com/beaver20007/docraft](https://github.com/beaver20007/docraft) |

**Stirling-PDF** ([github.com/Stirling-Tools/Stirling-PDF](https://github.com/Stirling-Tools/Stirling-PDF)): референс для **utilities**, не движок Extract и не отдельная кнопка в Docraft. Полезные операции (merge, compress) планируются **здесь**, нативно или через лёгкий sidecar.

Подробнее о трёх режимах экспорта: [`EXPORT_MODES.md`](./EXPORT_MODES.md).  
Контракт будущей автоматизации: [`DOCRAFT_API_HOOK.md`](./DOCRAFT_API_HOOK.md).

## Когда использовать Magical PDF после Docraft / Desktop Instructor

Используйте Magical PDF **после** того, как Docraft или Desktop Instructor уже выдали финальный PDF, если нужно:

- запретить копирование/выделение текста из PDF (визуально документ остаётся читаемым);
- получить вид «отсканированного» документа с печатями, подписями или вставленными картинками без отдельного текстового слоя;
- отдать ученику/клиенту **защищённую** копию, сохранив исходник с текстовым слоём у себя;
- пройти проверку «на глаз» через **Предпросмотр страниц** до скачивания (см. README).

**Не обязательно** гонять Magical PDF, если:

- нужен поиск по тексту, доступность (screen reader), малый размер файла;
- PDF уже финальный и текст должен оставаться выделяемым;
- достаточно обычного экспорта Docraft (режим 1 в `EXPORT_MODES.md`).

Типовой поток **Docraft + Magical**:

```text
Desktop Instructor / Docraft  →  экспорт PDF (текстовый слой)
        ↓
Magical PDF (Protect)         →  «Создать новый PDF» или JPEG ZIP
        ↓
Распространение защищённой копии
```

## Офлайн и облако

| Сценарий | Docraft / Desktop Instructor | Magical PDF |
|----------|------------------------------|-------------|
| **Облачный Docraft** | Генерация и экспорт PDF на серверах DOCRAFT; исходник может храниться в облаке | Обработка **только на устройстве пользователя**: web (браузер), Tauri (Windows/macOS), iOS. Файл в Magical не отправляется на backend Magical PDF |
| **Локальный / офлайн Docraft** | Экспорт PDF на диск без сети (если продукт это поддерживает) | Полностью офлайн на desktop/mobile сборках; web-версия тоже не требует сервера обработки, но нужен браузер |
| **Только Magical** | Не участвует | Пользователь открывает **любой** сторонний PDF локально (режим 3 в `EXPORT_MODES.md`) |

**Практика для авторов:** храните «мастер» с текстовым слоём в Docraft/облаке DOCRAFT; «защищённую» версию выпускайте через Magical на своём ПК или в доверенном браузере.

**Практика для разработчиков:** интеграция Docraft → Magical не должна подразумевать загрузку PDF на сервер Magical. Предпочтительны: передача файла по локальному пути, `file://` / нативный диалог, deep link «открыть в Magical» (см. `DOCRAFT_API_HOOK.md`).

## Ссылки

- Magical PDF (исходники): [github.com/beaver20007/magical-pdf](https://github.com/beaver20007/magical-pdf)
- Web preview (GitHub Pages): [beaver20007.github.io/magical-pdf](https://beaver20007.github.io/magical-pdf/)
- Планируемый продуктовый домен DOCRAFT: `https://app.docraft.pro` *(когда будет готов — см. отчёт по домену в задаче интеграции)*
- DOCRAFT meta-repo: [github.com/beaver20007/docraft](https://github.com/beaver20007/docraft)

## Статус интеграции

| Lane | Статус |
|------|--------|
| **Protect** | Ручная + web/Tauri; hook v0.1 в `DOCRAFT_API_HOOK.md` |
| **Utilities** | План: `PDF_UTILITIES_ROADMAP.md` (Stirling-class, в этом репо) |
| **Extract** | Разработка в ocr-docs; слияние после quality gates |

Docraft UI (будущее): одна точка входа «PDF» → deep link в magical-pdf (`mode=protect|tools|extract`), без встраивания Stirling в облако Create.

## Статус интеграции (Protect, сегодня)

На текущий момент связка **Protect документирована и ручная**: пользователь скачивает PDF из Docraft/Desktop Instructor и обрабатывает его в Magical PDF. Программный вызов (CLI, deep link, batch) описан в `DOCRAFT_API_HOOK.md` как спецификация без обязательной реализации в `app.js`.

# Magical PDF

Magical PDF превращает обычный PDF в визуально “сканированный” документ: каждая страница рендерится в JPEG, а затем из этих изображений собирается новый PDF без текстового слоя. Все операции выполняются локально на устройстве: PDF не отправляется на внешний сервер.

Публичная web-версия (GitHub Pages, авто-деплой с `main`):

```text
https://beaver20007.github.io/magical-pdf/
```

- **Защитить** — полностью в браузере, без сервера.
- **Распознать** — UI на Pages + облачный Extract API (бета). Настройка: [`docs/DEPLOY_EXTRACT.md`](docs/DEPLOY_EXTRACT.md).  
  Deploy API: [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://dashboard.render.com/select-repo?type=blueprint)

## Part of DOCRAFT ecosystem

Magical PDF — локальный **PDF-хаб** в [DOCRAFT](https://github.com/beaver20007/docraft): **Protect** (скан без текста) и **Extract** (скан → DOCX/PPTX, в разработке). Подробности: [`docs/DOCRAFT_INTEGRATION.md`](docs/DOCRAFT_INTEGRATION.md), Extract — [`docs/EXTRACT_INTEGRATION.md`](docs/EXTRACT_INTEGRATION.md), [`extract/README.md`](extract/README.md).

## Extract API (Phase 5.1+)

```powershell
cd extract
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\run-api.ps1
```

Сервис: `http://127.0.0.1:8765` — тот же контракт jobs, что в ocr-docs.

## Что уже умеет (Protect)

- Создаёт новый PDF из JPEG-страниц исходного PDF.
- Экспортирует страницы PDF в JPEG ZIP.
- Работает с одним PDF или несколькими PDF для пакетного JPEG-экспорта.
- Позволяет выбрать страницы для обработки: например `1-3, 7, 10-12`.
- Показывает предпросмотр страниц до скачивания (кнопка «Предпросмотр страниц»).
- Поддерживает три режима качества: низкое, среднее, высокое.
- Работает локально в браузере, Windows/macOS desktop-приложении и iOS-обёртке.
- Не отправляет документы на сервер.
- Использует локальные vendor-библиотеки, поэтому desktop/mobile сборки могут работать офлайн.

## Для кого

Magical PDF полезен, когда нужно:

- убрать выделяемый текстовый слой из PDF;
- сделать документ визуально похожим на скан;
- подготовить PDF с факсимиле, печатями, вставленными изображениями или статичным визуальным видом;
- получить JPEG-страницы документа;
- быстро обработать PDF без загрузки на сторонние сайты.

## Быстрый старт

Установить зависимости:

```bash
npm ci
```

Запустить локальную web-версию:

```bash
npm run dev:web
```

Открыть:

```text
http://127.0.0.1:5173/
```

## Основные команды

```bash
npm run dev:web        # локальная web-версия
npm run build:web      # статическая web-сборка в dist
npm run build:mac      # macOS .app/.dmg через Tauri
npm run build:windows  # Windows .exe installer через Tauri/NSIS
npm run prepare:ios    # подготовить iOS-проект
npm run open:ios       # открыть iOS-проект в Xcode
```

## Платформы

### Web

Web-версия работает полностью в браузере. Для хостинга нужно собрать `dist`:

```bash
npm run build:web
```

В `dist` попадают HTML/CSS/JS и локальные vendor-библиотеки.

### Windows

Windows installer собирается на Windows:

```bash
npm run build:windows
```

Результат:

```text
src-tauri/target/release/bundle/nsis/
```

### macOS

macOS app и DMG собираются через Tauri:

```bash
npm run build:mac
```

Результат:

```text
src-tauri/target/release/bundle/
```

### iOS

iOS-проект находится в `ios/App` и открывается через Xcode:

```bash
npm run prepare:ios
npm run open:ios
```

Для финальной установки на iPhone нужны Xcode, CocoaPods и Apple Developer signing.

## GitHub Actions

В проекте есть workflow:

```text
.github/workflows/build-installers.yml
```

Он собирает:

- `web-dist`
- macOS artifact
- Windows `.exe` artifact

Публикация web preview на GitHub Pages настроена в:

```text
.github/workflows/deploy-pages.yml
```

## Документация

- `docs/DOCRAFT_INTEGRATION.md` — Magical PDF как слой Protect в DOCRAFT.
- `docs/EXPORT_MODES.md` — режимы экспорта: Docraft, Docraft + Magical, только Magical.
- `docs/DOCRAFT_API_HOOK.md` — спецификация deep link / CLI (без реализации в app).
- `START_HERE.md` — быстрый старт для продолжения работы в Codex.
- `WINDOWS_SETUP.md` — настройка Windows-сборки.
- `IOS_SETUP.md` — настройка iOS-сборки.
- `docs/windows-pc-workflow-guide.pdf` — инструкция для Windows ПК.
- `docs/macos-workflow-guide.pdf` — инструкция для macOS.
- `docs/codex-connectors-setup.md` — настройка Codex-коннекторов.
- `docs/codex-mac-mini-m4-setup.pdf` — подготовка Mac Mini M4.

## Архитектура

- `index.html` — основной интерфейс.
- `styles.css` — визуальный стиль.
- `app.js` — логика PDF/JPEG/PDF, сохранения и платформенных сценариев.
- `vendor/` — локальные browser-библиотеки.
- `scripts/prepare-dist.mjs` — сборка web `dist`.
- `scripts/generate-tauri-icon.mjs` — генерация app icons.
- `src-tauri/` — Tauri desktop wrapper.
- `ios/App` — iOS workspace.

## Принципы проекта

- Документы обрабатываются локально.
- Один общий интерфейс для Web, Windows, macOS и iOS.
- Desktop/mobile сборки должны работать офлайн.
- Готовые installer-файлы не коммитятся в Git.
- Секреты, API keys и OAuth credentials не хранятся в репозитории.

## Ближайшее развитие

- Режимы “чистый скан” и “реалистичный скан”.
- Подпись, печать и водяной знак.
- Drag & drop reorder страниц.
- GitHub Releases для удобной публикации `.exe` и `.dmg`.

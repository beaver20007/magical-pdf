# Codex handoff

Проект: Magical PDF.

Репозиторий:

https://github.com/beaver20007/magical-pdf

Текущий публичный web preview:

https://beaver20007.github.io/magical-pdf/

## Что делает приложение

Приложение берет PDF, рендерит страницы в JPEG с выбранным качеством, а затем может собрать новый PDF только из изображений страниц. Цель: получить PDF, визуально похожий на скан, без выделяемого текстового слоя.

Также есть экспорт страниц PDF в JPEG ZIP.

## Текущий вариант дизайна

Активный дизайн: Listva-inspired.

Важные ассеты:

- `public/hero-listva.png` — hero-иллюстрация.
- `public/app-icon.png` — PNG-иконка для веб-интерфейса.
- `src-tauri/icons/icon.icns` — macOS icon.
- `styles.css` — текущий Listva-интерфейс.

## Основные команды

```bash
npm ci
npm run dev:web
npm run build:web
npm run build:mac
npm run build:windows
npm run prepare:ios
npm run open:ios
```

## Файлы

- `index.html` — основной UI.
- `styles.css` — стиль интерфейса.
- `app.js` — вся логика PDF/JPEG/PDF.
- `scripts/dev-server.mjs` — локальный dev server и fallback сохранения в Downloads.
- `scripts/prepare-dist.mjs` — сборка web `dist`.
- `scripts/generate-tauri-icon.mjs` — генерация app icons.
- `src-tauri/src/main.rs` — native save dialog и открытие Finder/Проводника после сохранения.
- `src-tauri/tauri.conf.json` — Tauri config.
- `ios/App` — Xcode workspace for iOS.
- `IOS_SETUP.md` — iOS build and signing instructions.
- `.github/workflows/deploy-pages.yml` — публикация web preview на GitHub Pages.
- `.github/workflows/build-installers.yml` — CI для web/macOS/Windows artifacts.

## Важный контекст

На Mac локально Windows `.exe` не собрался, потому что нет Windows target/toolchain/NSIS. Для `.exe` нужно собирать на Windows или через GitHub Actions `windows-latest`.

iOS-проект создан через Capacitor в `ios/App`. Для финальной сборки нужны Xcode, CocoaPods и Apple Developer подпись. Сохранение результата на iOS идет через `@capacitor/filesystem` и `@capacitor/share`: после нажатия `↓ Скачать` открывается системное меню iOS, где можно выбрать `Сохранить в Файлы`.

GitHub Actions уже настроен для Windows job:

```text
.github/workflows/build-installers.yml
```

Если нужно получить `.exe` быстрее всего, на Windows-компьютере выполнить:

```powershell
npm ci
npm run build:windows
```

или запустить workflow `Build installers` в GitHub Actions.

## Ожидаемые следующие задачи

- Собрать и проверить Windows `.exe`.
- Убедиться, что в Windows после сохранения открывается Проводник с выбранным файлом.
- При необходимости поправить NSIS metadata/icon/name.
- Собрать и проверить iOS-приложение на iPhone через Xcode.
- Позже перенести web preview с GitHub Pages на официальный хостинг и домен.

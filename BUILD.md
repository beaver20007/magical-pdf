# Сборка и публикация Magical PDF

## Web

```bash
npm install
npm run build:web
```

Для хостинга загрузить содержимое папки `dist`.

## macOS

Для локальной сборки нужен Rust/Cargo.

```bash
npm install
npm run build:mac
```

Результат будет в:

```text
src-tauri/target/release/bundle/dmg/
src-tauri/target/release/bundle/macos/
```

## Windows

Windows `.exe` лучше собирать на Windows.

```bash
npm install
npm run build:windows
```

Результат будет в:

```text
src-tauri/target/release/bundle/nsis/
```

## iOS

iOS не собирается в DMG. Для iPhone/iPad нужен iOS-проект и далее сборка через Xcode в `.ipa`.

```bash
npm install
npm run add:ios
npm run sync:ios
npm run open:ios
```

Если проект `ios/App` уже создан:

```bash
npm run prepare:ios
npm run open:ios
```

Для финальной сборки нужны Xcode, CocoaPods и Apple Developer подпись. Подробности: `IOS_SETUP.md`.

## Android

```bash
npm install
npm run add:android
npm run sync:mobile
npm run open:android
```

## GitHub Actions

Файл `.github/workflows/build-installers.yml` собирает:

- `web-dist` для хостинга;
- `macos-app-dmg` для macOS;
- `windows-exe` для Windows.

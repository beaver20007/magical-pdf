# Magical PDF: iOS сборка

Эта версия использует Capacitor: внутрь iOS-приложения кладется тот же интерфейс Magical PDF, те же локальные библиотеки и те же файлы `app.js`, `styles.css`, `index.html`.

## Что уже подготовлено

- iOS-проект создан в папке `ios/App`.
- Название приложения: `Magical PDF`.
- Bundle ID: `com.magicalpdf.app`.
- Иконка приложения подключена через `ios/App/App/Assets.xcassets/AppIcon.appiconset`.
- Результаты PDF/ZIP на iOS сохраняются через нативные плагины Capacitor:
  - `@capacitor/filesystem`;
  - `@capacitor/share`.

После нажатия `↓ Скачать` приложение открывает системное меню iOS. В нем можно выбрать `Сохранить в Файлы`, AirDrop, отправку в мессенджер, почту и другие доступные действия.

## Что нужно установить на Mac

1. Xcode из App Store.
2. Command Line Tools:

```bash
xcode-select --install
```

3. CocoaPods:

```bash
sudo gem install cocoapods
```

Если `gem` недоступен или ругается на права, можно установить через Homebrew:

```bash
brew install cocoapods
```

4. Apple Developer аккаунт для установки на реальный iPhone или публикации в App Store.

## Подготовить проект

```bash
npm install
npm run prepare:ios
npm run sync:ios
```

Если iOS-проект уже создан, обычно достаточно:

```bash
npm run sync:ios
```

## Открыть в Xcode

```bash
npm run open:ios
```

Или открыть вручную:

```text
ios/App/App.xcworkspace
```

Важно открывать именно `App.xcworkspace`, а не `App.xcodeproj`, потому что Capacitor-плагины подключаются через CocoaPods.

## Запуск на iPhone

1. Подключить iPhone к Mac.
2. В Xcode выбрать устройство сверху рядом с кнопкой Run.
3. Открыть Signing & Capabilities.
4. Выбрать Team.
5. При необходимости поменять Bundle Identifier на уникальный, например:

```text
com.petrtsvetkov.magicalpdf
```

6. Нажать Run.

## Сборка IPA

В Xcode:

1. Выбрать `Any iOS Device`.
2. Menu → Product → Archive.
3. После архивации нажать Distribute App.
4. Выбрать способ:
   - App Store Connect;
   - TestFlight;
   - Ad Hoc;
   - Development.

Для полноценной `.ipa` нужен Apple Developer аккаунт и корректная подпись.

## Проверка функционала

- PDF выбирается через системное окно iOS.
- `Создать новый PDF` делает файл без выделяемого текстового слоя.
- `Создать страницы JPEG` делает ZIP-архив.
- `↓ Скачать` открывает меню iOS, где можно сохранить файл в `Файлы`.
- Приложение работает офлайн после установки.

## Ограничение

На больших PDF высокое качество может требовать много памяти. Если iPhone закрывает приложение или страница не обрабатывается, сначала проверьте режим `Среднее`, затем уже оптимизируйте память рендера.

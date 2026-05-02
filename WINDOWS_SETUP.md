# Windows setup

Инструкция для продолжения разработки Magical PDF на Windows и сборки `.exe`.

## 1. Установить программы

Установите:

- Git: https://git-scm.com/download/win
- Node.js LTS: https://nodejs.org/
- Rust: https://www.rust-lang.org/tools/install
- Visual Studio Build Tools 2022: https://visualstudio.microsoft.com/visual-cpp-build-tools/

В Visual Studio Build Tools выберите workload:

- Desktop development with C++
- MSVC v143 build tools
- Windows 10/11 SDK

Tauri на Windows также использует WebView2. Обычно он уже есть в Windows 10/11. Если нет, установите Evergreen Runtime:

https://developer.microsoft.com/microsoft-edge/webview2/

## 2. Клонировать проект

Откройте PowerShell:

```powershell
cd $env:USERPROFILE\Documents
git clone https://github.com/beaver20007/magical-pdf.git
cd magical-pdf
```

## 3. Установить зависимости

```powershell
npm ci
```

## 4. Запустить веб-версию локально

```powershell
npm run dev:web
```

Откройте:

```text
http://127.0.0.1:5173/
```

## 5. Собрать Windows installer `.exe`

```powershell
npm run build:windows
```

Готовый installer появится здесь:

```text
src-tauri\target\release\bundle\nsis\
```

## 6. Если сборка не идет

Проверьте:

```powershell
node --version
npm --version
rustc --version
cargo --version
```

Если Rust установлен, но PowerShell его не видит, закройте PowerShell и откройте заново.

Если ошибка связана с Visual Studio/MSVC, откройте Visual Studio Installer и убедитесь, что установлен workload `Desktop development with C++`.

## 7. Продолжить работу в Codex на Windows

Откройте Codex на Windows, выберите папку:

```text
%USERPROFILE%\Documents\magical-pdf
```

Затем можно написать Codex:

```text
Продолжи работу над Magical PDF. Прочитай CODEX_HANDOFF.md и WINDOWS_SETUP.md, затем помоги собрать Windows .exe.
```


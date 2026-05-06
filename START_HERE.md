# Magical PDF: как быстро продолжить работу

Общий проект хранится здесь:

```text
https://github.com/beaver20007/magical-pdf
```

## Самый простой сценарий

1. Откройте Codex.
2. Выберите папку проекта:
   - Windows: `%USERPROFILE%\Documents\magical-pdf`
   - macOS: `~/Documents/magical-pdf`
3. Напишите Codex:

```text
Продолжи работу над Magical PDF. Сначала синхронизируй проект с GitHub, затем помоги с задачей.
```

## Ещё проще: стартовые скрипты

Перед открытием проекта в Codex можно запустить готовый скрипт:

- Windows: `scripts/start-windows.cmd`
- macOS: `scripts/start-macos.command`

Скрипт делает:

1. Переходит в папку проекта.
2. Переключается на `main`.
3. Подтягивает свежую версию из GitHub.
4. Устанавливает зависимости через `npm ci`.
5. Показывает путь, который нужно выбрать в Codex.

## Если проекта ещё нет на компьютере

Сначала один раз скачайте проект.

Windows PowerShell:

```powershell
cd $env:USERPROFILE\Documents
git clone https://github.com/beaver20007/magical-pdf.git
cd magical-pdf
scripts\start-windows.cmd
```

macOS Terminal:

```bash
cd ~/Documents
git clone https://github.com/beaver20007/magical-pdf.git
cd magical-pdf
chmod +x scripts/start-macos.command
./scripts/start-macos.command
```

## Главное правило

Перед работой подтянуть свежий `main`.
После законченной работы сделать commit и push.

Так любой компьютер продолжает с последнего общего состояния проекта.

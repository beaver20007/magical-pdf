# Codex Setup

Простая настройка глобальных коннекторов Codex на новом Windows-устройстве.

Цель: включить тот же набор коннекторов, который уже настроен на основном ПК, для всех проектов Codex.

## Что будет настроено

Скрипт включит в глобальном конфиге Codex:

- Google Drive
- Gmail
- Google Calendar
- Slack
- Notion
- Linear
- Teams

Файл настройки:

```text
C:\Users\<ваш_пользователь>\.codex\config.toml
```

## Что скрипт не делает

Скрипт не хранит и не вводит пароли, API-ключи и OAuth-токены.

После запуска нужно будет открыть Codex и, если он попросит, один раз подтвердить вход в сервисы:

- Google
- Slack
- Notion
- Linear
- Microsoft/Teams, если нужен Microsoft-блок

## Самая простая установка

1. Установите и откройте Codex на новом устройстве.
2. Войдите в тот же аккаунт Codex/OpenAI.
3. Скачайте или клонируйте этот репозиторий.
4. Откройте PowerShell в папке репозитория.
5. Запустите:

```powershell
.\scripts\setup-codex-connectors.ps1
```

6. Перезапустите Codex.
7. Откройте настройки коннекторов Codex и подтвердите авторизации, если они потребуются.
8. Проверьте установку:

```powershell
.\scripts\verify-codex-connectors.ps1
```

## Если PowerShell запрещает запуск скрипта

Запустите команду только для текущего окна PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Затем снова выполните:

```powershell
.\scripts\setup-codex-connectors.ps1
```

Или запустите setup одной командой без изменения политики PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-codex-connectors.ps1
```

## Безопасность

- Скрипт делает резервную копию `config.toml` перед изменением.
- Скрипт добавляет только недостающие секции `[plugins...]`.
- Скрипт не удаляет существующие настройки.
- Скрипт не записывает секреты в файлы.
- API-ключи для HubSpot, Stripe, Apollo и других сервисов нужно хранить отдельно в безопасном менеджере паролей.

## Что делать после установки

В Codex попросите:

```text
Проверь, что Google Drive, Gmail, Google Calendar, Slack, Notion и Linear доступны как глобальные коннекторы.
```

Codex должен проверить доступ read-only способом: профиль, список доступных инструментов или безопасный поиск без изменений данных.

## Откуда берутся эти файлы на другом устройстве

Другой компьютер сможет скачать эту папку только после того, как изменения будут сохранены в GitHub.

Перед настройкой нового устройства на основном ПК нужно сделать:

```text
Попросить Codex закоммитить и отправить в GitHub папку codex-setup и инструкцию docs/codex-mac-mini-m4-setup.pdf/html.
```

После успешного push на новом устройстве можно выполнить:

```powershell
git clone https://github.com/beaver20007/magical-pdf.git
cd magical-pdf\codex-setup
```

Если папка `codex-setup` будет вынесена в отдельный репозиторий, клонировать нужно будет уже его.

# Инструкция для Codex на новом устройстве

Ты настраиваешь глобальные коннекторы Codex на новом Windows-устройстве пользователя.

Работай максимально аккуратно: не удаляй существующие настройки, не трогай секреты, не записывай API-ключи в репозиторий.

## Задача

1. Убедись, что пользователь скачал или клонировал репозиторий из GitHub.
2. Найди папку этого репозитория.
3. Запусти скрипт:

```powershell
.\scripts\setup-codex-connectors.ps1
```

4. Если запуск PowerShell-скриптов запрещен, предложи пользователю выполнить:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

После этого повтори запуск setup-скрипта.

5. Проверь результат:

```powershell
.\scripts\verify-codex-connectors.ps1
```

6. Попроси пользователя перезапустить Codex, если Codex еще не видит новые плагины.

## Источник файлов

Эта инструкция и скрипты должны прийти из GitHub-репозитория пользователя.

Ожидаемый вариант:

```text
https://github.com/beaver20007/magical-pdf
```

Папка:

```text
magical-pdf/codex-setup
```

Если папки `codex-setup` нет, значит изменения еще не были закоммичены и отправлены в GitHub с основного устройства. В этом случае объясни пользователю, что сначала нужно вернуться на основной ПК и попросить Codex выполнить commit/push.

## Ожидаемые глобальные плагины

В файле `%USERPROFILE%\.codex\config.toml` должны быть включены:

```toml
[plugins."google-drive@openai-curated"]
enabled = true

[plugins."gmail@openai-curated"]
enabled = true

[plugins."google-calendar@openai-curated"]
enabled = true

[plugins."slack@openai-curated"]
enabled = true

[plugins."notion@openai-curated"]
enabled = true

[plugins."linear@openai-curated"]
enabled = true

[plugins."teams@openai-curated"]
enabled = true
```

Эти секции должны быть на верхнем уровне `config.toml`, а не внутри `[projects...]`.

## Проверка после перезапуска Codex

Используй доступные инструменты Codex/tool search, чтобы проверить:

- Google Drive tools доступны
- Gmail profile читается
- Google Calendar profile читается
- Slack tools доступны
- Notion tools доступны
- Linear tools доступны

Делай только безопасные проверки без изменения данных. Не отправляй письма, не создавай события, не меняй задачи и страницы без явной просьбы пользователя.

## Если OAuth не подтянулся

Если плагин включен, но коннектор просит авторизацию:

1. Скажи пользователю, какой сервис требует вход.
2. Попроси открыть Codex settings -> Connectors.
3. Попроси нажать Connect/Auth для нужного сервиса.
4. После авторизации повтори read-only проверку.

## Важные ограничения

- Не пытайся обходить OAuth.
- Не проси пользователя присылать пароли.
- Не записывай токены в `config.toml`.
- Не коммить секреты.
- Для HubSpot, Stripe, Apollo, Intercom, MailerLite, Make, Zapier, n8n, Canva, Gamma, Granola и Clay нужны отдельные API/OAuth-настройки.

# Чеклист коннекторов Codex

## Готовые marketplace-коннекторы

| Сервис | Статус | Что проверить |
| --- | --- | --- |
| Google Drive | Включить глобально | Доступны инструменты Drive/Docs/Sheets/Slides |
| Gmail | Включить глобально | Читается Gmail profile |
| Google Calendar | Включить глобально | Читается Calendar profile |
| Slack | Включить глобально | Доступны Slack tools |
| Notion | Включить глобально | Доступны Notion tools |
| Linear | Включить глобально | Доступны Linear tools |
| Teams | Включить глобально | Требуется Microsoft-аккаунт |

## OAuth может потребовать ручного подтверждения

- Google: Drive, Gmail, Calendar
- Slack
- Notion
- Linear
- Microsoft Teams

## Оставшиеся сервисы через API/MCP

Эти сервисы нельзя полностью подключить одним локальным скриптом без токенов или OAuth-настроек:

- HubSpot
- Canva
- Apollo.io
- Clay
- Asana
- n8n
- Zapier
- Make
- Stripe
- Intercom
- Gamma
- Granola
- MailerLite

Для них нужны API keys, OAuth credentials или webhook URLs.

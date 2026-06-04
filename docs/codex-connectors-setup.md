# Настройка коннекторов Codex

Этот документ фиксирует план подключения коннекторов из скриншота, текущий статус и то, что нужно для оставшихся интеграций.

## Уже включено в Codex

- Slack
- Notion
- Linear
- Google Drive
- Gmail
- Google Calendar
- Teams: плагин есть в конфиге, но для полноценной авторизации нужен Microsoft-аккаунт

## Глобальное использование

Текущие коннекторы включены в глобальном конфиге Codex на этом ПК:

- `C:\Users\tsvetkov\.codex\config.toml`

Они прописаны в секциях `[plugins...]` верхнего уровня, а не внутри конкретного проекта. Это значит, что на этом устройстве они доступны во всех проектах Codex, а не только в `magical-pdf`.

Важно по другим устройствам:

- Marketplace-плагины и OAuth-доступы обычно привязаны к аккаунту Codex/OpenAI и могут появляться после входа в тот же аккаунт.
- Локальный файл `config.toml` находится на конкретном устройстве и сам по себе не гарантирует перенос настроек на другой компьютер.
- На новом устройстве нужно войти в тот же аккаунт Codex, открыть настройки коннекторов и проверить, что Google Drive, Gmail, Google Calendar, Slack, Notion и Linear включены.
- Если какой-то коннектор не появился автоматически, его нужно подключить повторно через Codex settings. OAuth-разрешения Google/Slack/Notion/Linear могут потребовать повторного подтверждения.
- Ручные MCP/API-коннекторы, которые будут добавляться позже через ключи и токены, нужно будет отдельно настроить на каждом устройстве или хранить в синхронизируемом безопасном хранилище секретов.

## Инструкция для Mac Mini M4

Для нового Mac Mini M4 подготовлена отдельная инструкция:

- `docs/codex-mac-mini-m4-setup.html`
- `docs/codex-mac-mini-m4-setup.pdf`

Важно: эти файлы и папка `codex-setup` будут доступны на другом устройстве через GitHub только после commit и push текущих изменений.

## Почему Codex не может сам завершить все подключения

Codex может включать marketplace-плагины, если они есть в текущем каталоге Codex. Для оставшихся сервисов в этой среде нет готовых installable-коннекторов Codex, поэтому нужен ручной путь через MCP/API.

Для ручного подключения через API или MCP Codex все равно должен получить от владельца аккаунта один из следующих доступов:

- OAuth-авторизация в браузере
- API key или personal access token
- Webhook URL
- Доступ к функциям платного тарифа, если сервис ограничивает API по тарифу

Codex не должен угадывать, извлекать или обходить такие учетные данные. Когда нужные ключи или OAuth-доступы будут предоставлены, Codex сможет добавить MCP/API-конфигурацию, проверить read-only запросы и описать доступные действия.

## Google-блок, подключен

Сервисы:

- Google Drive
- Gmail
- Google Calendar

Статус:

- Подключенный Google-аккаунт: beaver20007@gmail.com
- Проверка Gmail-профиля прошла успешно
- Проверка Google Calendar-профиля прошла успешно
- Инструменты Google Drive доступны в Codex

Доступные возможности Google:

- Поиск и работа с Drive, Docs, Sheets и Slides
- Чтение профиля Gmail, поиск писем, создание черновиков, отправка писем только по явной просьбе
- Чтение профиля Google Calendar, поиск событий, проверка доступности, ответы на приглашения только по явной просьбе

## Microsoft-блок для личного использования

Сервисы:

- Outlook Email
- Outlook Calendar
- Teams
- SharePoint, если доступен для выбранного типа аккаунта

Простая схема регистрации личного аккаунта:

1. Создать Microsoft-аккаунт на https://signup.live.com/.
2. При желании использовать существующий Gmail-адрес. Новый Outlook-адрес заводить необязательно.
3. Подтвердить email и телефон, если Microsoft попросит.
4. Один раз войти на https://account.microsoft.com/ и проверить, что аккаунт активен.
5. Один раз открыть https://outlook.live.com/, чтобы инициализировать почту и календарь Outlook.
6. Один раз открыть https://teams.microsoft.com/, чтобы инициализировать Teams.
7. Вернуться в настройки Codex и подключить Outlook Email, Outlook Calendar и Teams.
8. После этого попробовать подключить SharePoint. Если SharePoint недоступен, считать его требующим рабочий или учебный Microsoft 365-аккаунт.

## Оставшиеся 13 коннекторов

### HubSpot

Лучший путь: private app token для личного или внутреннего использования.

Что нужно сделать пользователю:

1. Войти в HubSpot.
2. Перейти в Settings -> Integrations -> Private Apps.
3. Создать private app для Codex.
4. Выдать минимально необходимые CRM scopes.
5. Скопировать private app access token.
6. Передать токен Codex через безопасный механизм секретов, не через файлы репозитория.

После этого Codex сможет настроить HubSpot MCP/API-обертку и проверить read-only запрос.

### Canva

Лучший путь: Canva Connect API через OAuth.

Примечания:

- Публичные интеграции требуют проверки Canva.
- Private integrations рассчитаны на team/Enterprise-использование.
- Codex может подготовить OAuth/API-клиент, но пользователь должен создать интеграцию Canva и подтвердить доступ.

Что нужно предоставить:

- Client ID
- Client secret
- OAuth redirect configuration
- Approved scopes

### Apollo.io

Лучший путь: Apollo API key.

Что нужно сделать пользователю:

1. Открыть Apollo.
2. Перейти в Settings -> Integrations.
3. Подключить Apollo API.
4. Создать API key с нужными endpoints.
5. Скопировать ключ один раз и сохранить его безопасно.

Доступ к API может зависеть от тарифа Apollo.

### Clay

Лучший путь: интеграция через webhook.

Варианты:

- Отправлять данные в Clay tables через webhook.
- Использовать Make, Zapier или n8n как промежуточный слой.
- Использовать Enterprise People and Company API только если аккаунт имеет Enterprise-доступ.

Что нужно предоставить:

- Clay webhook URL
- Опциональный webhook auth token
- Нужную схему таблицы или пример payload

### Asana

Лучший путь: personal access token для личного или внутреннего использования.

Что нужно сделать пользователю:

1. Открыть Asana developer console.
2. Создать personal access token.
3. Скопировать его один раз и сохранить безопасно.
4. Передать токен Codex через безопасный механизм секретов.

Для публичных или multi-user приложений лучше использовать OAuth вместо personal access token.

### n8n

Лучший путь: n8n API key или webhook.

Важно:

- Public API n8n недоступен во время free trial.

Что нужно предоставить:

- URL n8n-инстанса
- API key из Settings -> n8n API
- Или workflow webhook URLs

### Zapier

Лучший путь: webhook или Zapier API workflow.

Примечания:

- API-функции Zapier могут требовать платный тариф.
- Для многих простых автоматизаций достаточно Zapier Catch Hook URL.

Что нужно предоставить:

- Catch Hook URL
- Или Zapier OAuth/client details для API workflows

### Make

Лучший путь: Make API token или webhook.

Что нужно сделать пользователю:

1. Войти в Make.
2. Открыть Profile -> API.
3. Добавить token.
4. Выбрать минимальные scopes.
5. Скопировать token один раз и сохранить безопасно.

Что нужно Codex:

- Make zone/base URL, если применимо
- API token или scenario webhook URL

### Stripe

Лучший путь: restricted API key сначала в test mode.

Что нужно сделать пользователю:

1. Открыть Stripe Dashboard -> Developers -> API keys.
2. Сначала использовать test mode.
3. Создать restricted key с минимальными read-only scopes, если возможно.
4. Для webhooks дополнительно скопировать webhook signing secret.

Не использовать live secret keys до проверки интеграции.

### Intercom

Лучший путь: private app access token.

Что нужно сделать пользователю:

1. Открыть Intercom Developer Hub.
2. Создать app в workspace.
3. Открыть Configure -> Authentication.
4. Скопировать access token.
5. Передать токен Codex через безопасный механизм секретов.

Для публичных или multi-workspace приложений лучше использовать OAuth.

### Gamma

Лучший путь: Gamma Generate API key.

Важно:

- Доступ к API требует тариф Pro, Ultra, Team или Business.

Что нужно сделать пользователю:

1. Открыть Gamma Settings and Members.
2. Открыть вкладку API key.
3. Создать API key.
4. Скопировать ключ и сохранить безопасно.

Gamma API keys передаются через заголовок `X-API-KEY`.

### Granola

Лучший путь: Enterprise API key.

Важно:

- Доступ к Granola API предназначен для администраторов Enterprise workspace.
- API дает read-доступ к доступным или shared meeting notes.

Что нужно предоставить:

- Granola Enterprise API key
- Ожидания по доступу к workspace

Если Enterprise-тарифа нет, использовать ручной экспорт или automation bridge, если он доступен в аккаунте Granola.

### MailerLite

Лучший путь: MailerLite API token.

Что нужно сделать пользователю:

1. Открыть MailerLite.
2. Перейти в Integrations.
3. Выбрать MailerLite API.
4. Сгенерировать новый token.
5. Сразу скопировать его.

Использовать новый MailerLite API, если аккаунт не относится к MailerLite Classic.

## Рекомендуемый порядок

1. Microsoft: создать личный Microsoft-аккаунт и подключить Outlook/Teams, если эти сервисы нужны.
2. Сначала подключить сервисы с API-ключами: Asana, Apollo, MailerLite, Stripe test mode, Intercom, HubSpot.
3. Затем подключить automation hubs: n8n, Make, Zapier.
4. После этого перейти к gated/special сервисам: Canva, Gamma, Granola, Clay Enterprise.

## Чеклист безопасной передачи доступов для Codex

Для каждого сервиса нужно указать:

- Название сервиса
- Тариф аккаунта
- API token или OAuth credentials через безопасное хранилище секретов
- Разрешенные операции: только чтение, создание/обновление, отправка сообщений, управление billing и так далее
- Один тестовый сценарий, который Codex должен выполнить после настройки

Никогда не коммитить API keys в этот репозиторий.

# DOCRAFT → Magical PDF: контракт интеграции (спецификация)

**Статус:** specification only. Текущий `app.js` не обязан реализовывать этот контракт; документ задаёт целевые интерфейсы для Docraft, Desktop Instructor и meta-repo DOCRAFT.

## Цель

После экспорта PDF из Docraft автоматически или полуавтоматически передать файл в Magical PDF (слой **Protect**) без загрузки содержимого на сервер Magical.

## Входные данные

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `input` | `path` \| `bytes` \| `file_uri` | Да | Исходный PDF |
| `pages` | `string` | Нет | Диапазон страниц, как в UI: `1-3, 7, 10-12` или пусто = все |
| `quality` | `"low"` \| `"medium"` \| `"high"` | Нет | Пресет DPI/JPEG; по умолчанию `high` |
| `output_mode` | `"pdf"` \| `"jpeg_zip"` | Нет | Результат: новый PDF-скан или ZIP JPEG-страниц |
| `suggested_filename` | `string` | Нет | Имя для сохранения без пути |
| `correlation_id` | `string` (UUID) | Нет | Связь с задачей/уроком в Docraft для логов (без PII в URL) |

### `input` — форматы

- **`path`:** абсолютный или относительный путь на диске (desktop, CI). Пример: `C:\Users\...\Exports\lesson-03.pdf`
- **`bytes`:** сырой PDF в памяти (будущий CLI stdin / IPC)
- **`file_uri`:** `file:///...` или платформенный URI после sandboxed picker (iOS/Android)

Максимальный размер и таймаут — на стороне вызывающего продукта; Magical PDF обрабатывает файл синхронно в UI-потоке (см. текущую реализацию рендера).

## Выходные данные (целевые)

| Поле | Тип | Описание |
|------|-----|----------|
| `output_path` | `string` | Путь к записанному PDF или ZIP |
| `page_count` | `number` | Число обработанных страниц |
| `byte_size` | `number` | Размер результата |
| `status` | `"ok"` \| `"error"` | Итог |
| `error_message` | `string` | Человекочитаемая ошибка при `status=error` |

## Способы вызова (приоритет внедрения)

### 1. Deep link / custom URL scheme (web и desktop)

**Назначение:** Desktop Instructor или Docraft web открывает Magical с подсказкой файла.

Предлагаемая схема (черновик):

```text
magical-pdf://open?source=docraft&correlation_id={uuid}
https://beaver20007.github.io/magical-pdf/?source=docraft&return_url={encoded}
```

Параметры query (web):

| Параметр | Описание |
|----------|----------|
| `source` | Всегда `docraft` для аналитики и UX-подсказок |
| `pages` | URL-encoded диапазон страниц |
| `quality` | `low` \| `medium` \| `high` |
| `return_url` | Опционально: куда вернуть пользователя после скачивания (только https) |

**Ограничение безопасности:** браузер не передаёт локальный `path` в query; пользователь **выбирает файл** в Magical или получает файл через `download` + drag-and-drop. Docraft может отдать blob через «Скачать» и подсказку «Открыть в Magical PDF».

### 2. CLI (desktop, CI, будущий пакет)

**Назначение:** пакетная постобработка на Windows/macOS без GUI.

Черновик интерфейса:

```bash
magical-pdf protect \
  --input /path/to/in.pdf \
  --output /path/to/out-scan.pdf \
  --pages "1-10" \
  --quality high
```

```bash
magical-pdf protect \
  --input - \
  --output - \
  --output-mode jpeg_zip < in.pdf > pages.zip
```

Коды выхода: `0` — успех, `1` — ошибка валидации, `2` — ошибка рендера/IO.

Реализация: отдельный бинарь (Tauri sidecar или Node script), **не** обязательна в текущем репозитории.

### 3. «Скачать и обработать в Magical» (ручной, текущий MVP)

**Назначение:** уже поддерживаемый сценарий без изменений кода.

1. Docraft / Desktop Instructor → экспорт PDF (режим 1).
2. Пользователь открывает Magical PDF (web или desktop).
3. Выбор файла → Предпросмотр (опционально) → Создать новый PDF → Скачать.

Docraft UI может показывать кнопку «Защитить в Magical PDF» со ссылкой на web preview или на установленный `.app` / `.exe`.

## События (опционально, для meta-repo)

Для телеметрии продукта (без содержимого PDF):

```json
{
  "event": "magical_protect_completed",
  "correlation_id": "uuid",
  "source": "docraft",
  "page_count": 12,
  "quality": "high",
  "duration_ms": 4500
}
```

Отправка — только с согласия пользователя и политики DOCRAFT; Magical PDF сегодня **не** отправляет такие события.

## Версионирование контракта

| Версия | Дата | Изменения |
|--------|------|-----------|
| `0.1` | 2026-06-04 | Первая спецификация: вход path/bytes, deep link черновик, CLI черновик, ручной MVP |

При реализации в `app.js` или Tauri добавить поле `api_version` в ответ CLI и changelog в DOCRAFT meta-repo.

## Связанные документы

- [`DOCRAFT_INTEGRATION.md`](./DOCRAFT_INTEGRATION.md)
- [`EXPORT_MODES.md`](./EXPORT_MODES.md)

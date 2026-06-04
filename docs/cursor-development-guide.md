# Magical PDF: продолжение разработки в Cursor

Эта инструкция нужна, чтобы открыть общий проект Magical PDF в Cursor и продолжить работу с актуального состояния GitHub.

Репозиторий проекта:

```text
https://github.com/beaver20007/magical-pdf
```

## 1. Если проекта ещё нет на компьютере

Откройте Terminal или PowerShell и выполните:

```bash
cd ~/Documents
git clone https://github.com/beaver20007/magical-pdf.git
cd magical-pdf
npm ci
```

На Windows вместо `~/Documents` используйте:

```powershell
cd $env:USERPROFILE\Documents
git clone https://github.com/beaver20007/magical-pdf.git
cd magical-pdf
npm.cmd ci
```

## 2. Если проект уже есть на компьютере

Перед открытием в Cursor обновите проект:

```bash
cd путь/к/magical-pdf
git switch main
git pull --ff-only origin main
npm ci
```

На Windows:

```powershell
cd $env:USERPROFILE\Documents\magical-pdf
git switch main
git pull --ff-only origin main
npm.cmd ci
```

## 3. Как открыть проект в Cursor

1. Откройте Cursor.
2. Нажмите `File`.
3. Нажмите `Open Folder`.
4. Выберите папку `magical-pdf`.
5. Дождитесь, пока Cursor откроет файлы проекта.
6. Откройте встроенный терминал Cursor: `Terminal` -> `New Terminal`.
7. Проверьте состояние проекта:

```bash
git status
git branch --show-current
```

Ожидаемо:

- ветка `main`;
- нет незнакомых незакоммиченных изменений, если вы начинаете новую задачу;
- если изменения есть, сначала понять, откуда они и нужны ли они.

## 4. Какие файлы прочитать в начале

Перед разработкой откройте и прочитайте:

```text
START_HERE.md
CODEX_HANDOFF.md
README.md
docs/codex-connectors-setup.md
```

Если работаете на Mac Mini M4, дополнительно:

```text
docs/codex-mac-mini-m4-setup.html
docs/codex-mac-mini-m4-setup.pdf
```

## 5. Основные команды проекта

Локальная web-версия:

```bash
npm run dev:web
```

Открыть в браузере:

```text
http://127.0.0.1:5173/
```

Web-сборка:

```bash
npm run build:web
```

Windows installer:

```bash
npm run build:windows
```

macOS app:

```bash
npm run build:mac
```

iOS:

```bash
npm run prepare:ios
npm run open:ios
```

## 6. Правила разработки

- Не откатывать чужие изменения без явного разрешения.
- Не коммитить `node_modules`, `dist`, `src-tauri/target`, `.exe`, `.dmg`, `.app`.
- Не коммитить API keys, OAuth tokens, пароли и другие секреты.
- Перед началом работы делать `git pull --ff-only origin main`.
- После законченной задачи делать commit и push.
- Для крупных задач лучше создавать отдельную ветку.

## 7. Как сохранить работу в GitHub

Проверить изменения:

```bash
git status
git diff --stat
```

Добавить изменения:

```bash
git add нужные-файлы
```

Создать commit:

```bash
git commit -m "Короткое описание изменения"
```

Отправить в GitHub:

```bash
git push origin main
```

Если задача крупная, лучше через ветку:

```bash
git switch -c feature/task-name
git add нужные-файлы
git commit -m "Describe change"
git push -u origin feature/task-name
```

Затем открыть Pull Request на GitHub.

## 8. Стартовый промт для Cursor

Скопируйте этот текст в Cursor Chat:

```text
Продолжи разработку проекта Magical PDF.

Репозиторий:
https://github.com/beaver20007/magical-pdf

Локальная папка проекта:
укажи текущую папку magical-pdf, открытую в Cursor

Сначала сделай:
1. Проверь git status.
2. Проверь текущую ветку.
3. Если ветка main и рабочее дерево чистое, подтяни свежий main через git pull --ff-only origin main.
4. Прочитай START_HERE.md, CODEX_HANDOFF.md, README.md и docs/codex-connectors-setup.md.
5. Кратко опиши текущее состояние проекта и только потом предлагай следующий шаг.

Важные правила:
- Не откатывай существующие изменения без моего явного разрешения.
- Не коммить секреты, API keys, tokens, node_modules, dist, target, .exe, .dmg или .app.
- Для крупных задач работай через отдельную ветку.
- После готовой задачи предложи commit/push или Pull Request.
- Если видишь незакоммиченные изменения, сначала объясни, что это за изменения, и спроси, как с ними поступить.

Текущая цель:
продолжить развитие Magical PDF как локального PDF-инструмента для Web, Windows, macOS и iOS.
```

## 9. Промт для продолжения после переполнения контекста

```text
Продолжи работу над Magical PDF после предыдущего окна.

Сначала:
1. Проверь git status.
2. Проверь текущую ветку.
3. Прочитай последние 5 коммитов.
4. Прочитай START_HERE.md, CODEX_HANDOFF.md и README.md.
5. Найди незавершённые изменения, если они есть, и кратко объясни их.

Не откатывай изменения без разрешения.
Продолжай с последней незавершённой задачи.
```

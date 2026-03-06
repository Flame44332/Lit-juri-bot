# LIT 1533 - Telegram-бот жюри + веб-панель

## 1) Запуск с нуля после распаковки архива (Windows и Linux)

### Что нужно заранее
- Python `3.10+`
- Интернет для установки зависимостей

### Про `seed.py` (тестовые песни)
Если нужно быстро заполнить классы тестовыми песнями, используйте:
```bash
python3 seed.py --force
```
На Windows:
```powershell
python seed.py --force
```
Обычно это делают сразу после первого запуска проекта или перед тестом.

### Шаг 0. Создать бота через `@BotFather` (для Telegram-режима)
1. В Telegram откройте `@BotFather`.
2. Отправьте команду `/newbot`.
3. Задайте имя бота и username (username должен заканчиваться на `bot`).
4. Скопируйте выданный токен - это значение для `BOT_TOKEN` в `.env`.

### Шаг 0.1 Узнать `SUPERADMIN_TELEGRAM_ID`
1. Откройте в Telegram бота `@userinfobot` (или аналог, который показывает ваш ID).
2. Отправьте любое сообщение.
3. Скопируйте числовой `id` - это значение для `SUPERADMIN_TELEGRAM_ID` в `.env`.

### Как заполнить `.env`
Скопируйте шаблон из `.env.example`:
```bash
cp .env.example .env
```

На Windows (PowerShell):
```powershell
Copy-Item .env.example .env
```

Дальше откройте `.env` и заполните минимум:
```env
BOT_TOKEN=1234567890:AA...
SUPERADMIN_TELEGRAM_ID=123456789
CLASS_PARALLELS=9-11
```

Если нужен только веб-режим без Telegram:
```env
BOT_DISABLED=1
```
Тогда `BOT_TOKEN` и `SUPERADMIN_TELEGRAM_ID` не обязательны. Полный список переменных - в `.env.example` и в разделе `6) Переменные окружения`.

### Windows (PowerShell)
1. Распакуйте архив и откройте PowerShell в папке проекта.
2. Создайте виртуальное окружение:
```powershell
py -3 -m venv .venv
```
3. Активируйте его:
```powershell
.\.venv\Scripts\Activate.ps1
```
4. Установите зависимости:
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
5. Создайте и заполните `.env` по блоку выше `Как заполнить .env`.
6. Запустите проект:
```powershell
python main.py
```
7. Для остановки: `Ctrl + C`.

### Linux (bash)
1. Распакуйте архив и перейдите в папку проекта:
```bash
cd /path/to/juri-bot
```
2. Создайте виртуальное окружение:
```bash
python3 -m venv .venv
```
3. Активируйте его:
```bash
source .venv/bin/activate
```
4. Установите зависимости:
```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```
5. Создайте и заполните `.env` по блоку выше `Как заполнить .env`.
6. Запустите проект:
```bash
python3 main.py
```
7. Для остановки: `Ctrl + C`.

После запуска всегда доступен Telegram-бот.
Если включен `WEB_ENABLED=1`, дополнительно доступны:
- веб-экран результатов: `http://<SERVER_IP>:8080/index.html`
- веб-голосование жюри: `http://<SERVER_IP>:8080/vote.html`
- веб-админка: `http://<SERVER_IP>:8080/admin.html`

## 2) Как пользоваться ботом (приоритетно)

### Для администратора (Telegram)
1. Супер-админ (ID из `SUPERADMIN_TELEGRAM_ID`) отправляет `/start` и попадает в `Админ-панель`.
2. Откройте `Пользователи` -> `Коды приглашений` и создайте код для жюри (одноразовый или многоразовый).
3. Перед выступлениями заполните `Классы и песни` и, при необходимости, `Очередь выступлений`.
4. Управление голосованием:
- `Управление голосованием` -> `Открыть голосование` (или `Следующий по очереди`)
- во время голосования можно нажать `Напомнить жюри`
- после выступления: `Закрыть голосование`
5. Контроль итогов:
- `Результаты` -> `Промежуточные результаты`
- `Результаты` -> `Финальные результаты` (после завершения всех классов или принудительно)
6. Сервис:
- `Настройки/Сервис` -> `Экспорт CSV`
- `Настройки/Сервис` -> `Логи действий`
- `Настройки/Сервис` -> `Сбросить голоса` (двойное подтверждение)

### Для жюри (Telegram)
1. Отправьте `/start`.
2. Вступите по коду: отправьте `/join`, затем следующим сообщением сам код.
3. Нажмите `Голосовать` -> выберите параллель -> класс.
4. Поставьте оценки по доступным критериям.
5. Дополнительно доступны:
- `Мои оценки`
- `Промежуточные итоги`
- `Статус выступлений`
- `Помощь`

Важно:
- Голосование доступно только по открытому классу.
- Одновременно может быть открыт только один класс.

## 3) Как пользоваться системой через веб

### Жюри (веб)
1. Откройте `http://<SERVER_IP>:8080/vote.html`.
2. Введите код жюри и имя (для логов).
3. Выберите класс и выставляйте оценки по критериям.

### Администратор (веб)
1. Создайте админ-аккаунт в Telegram-боте: `Пользователи` -> `Создать админ-аккаунт`.
2. Откройте `http://<SERVER_IP>:8080/admin.html`.
3. Войдите по `username/password` админ-аккаунта.
4. Используйте разделы: классы, очередь, критерии, пользователи, голосование, результаты, экспорт, логи, сброс.

### Экран результатов
- Откройте `http://<SERVER_IP>:8080/index.html` для проектора/экрана.

## 4) Режимы запуска

### Основной режим (Telegram + Web)
```bash
python3 main.py
```
(`python main.py` на Windows)

### Только Web (без Telegram)
Используйте, когда Telegram недоступен:
```env
BOT_DISABLED=1
WEB_ENABLED=1
WEB_HOST=0.0.0.0
WEB_PORT=8080
```
Запуск:
```bash
python3 web_only.py
```

### Webhook вместо polling
```env
BOT_MODE=webhook
WEBHOOK_URL=https://YOUR_DOMAIN_OR_IP:8443/webhook
WEBHOOK_PATH=/webhook
WEBHOOK_LISTEN=0.0.0.0
WEBHOOK_PORT=8443
WEBHOOK_CERT=/path/to/fullchain.pem
WEBHOOK_KEY=/path/to/privkey.pem
WEBHOOK_SECRET=
```
Если нужен обычный режим:
```env
BOT_MODE=polling
```

## 5) Команды Telegram
- `/start` - открыть меню по роли
- `/join` - начать вход жюри по коду (код отправляется следующим сообщением)
- `/link login password` - привязать Telegram-пользователя к админ-аккаунту

## 6) Переменные окружения (`.env`)
- `BOT_TOKEN` - токен Telegram-бота (обязательно, если `BOT_DISABLED=0`)
- `SUPERADMIN_TELEGRAM_ID` - Telegram ID супер-админа (обязательно, если `BOT_DISABLED=0`)
- `BOT_DISABLED` - `1` для запуска без Telegram-бота
- `DB_PATH` - путь к SQLite БД (по умолчанию `juri_bot.sqlite3`)
- `CLASS_PARALLELS` - диапазон параллелей для автосоздания классов на пустой БД (например `9-11` или `5-8`)
- `SESSION_TTL_SECONDS` - TTL сессий ввода в секундах (по умолчанию `1800`)
- `LOG_CHANNEL_ID` - канал/чат для аудита (опционально)
- `WEB_ENABLED` - включение веб-сервера (`1`/`0`)
- `WEB_HOST`, `WEB_PORT` - адрес и порт веб-сервера
- `WEB_DIR` - директория веб-статик-файлов
- `WEB_RESULTS_PATH` - путь до `results.json`
- `WEB_JURY_CODES` - список кодов жюри для web-only входа (через запятую, опционально)
- `BOT_MODE` - `polling` или `webhook`
- `WEBHOOK_URL`, `WEBHOOK_PATH`, `WEBHOOK_LISTEN`, `WEBHOOK_PORT`, `WEBHOOK_CERT`, `WEBHOOK_KEY`, `WEBHOOK_SECRET` - настройки webhook

## 7) Что создается автоматически
- SQLite БД и таблицы при первом запуске
- классы по `CLASS_PARALLELS`:
  `9-11` -> `9.1`-`11.6`, `5-8` -> `5.1`-`8.6`
- базовый набор критериев (11 штук с диапазонами баллов)

## 8) Полезные файлы
- `main.py` - запуск Telegram-бота (и web-сервера)
- `web_only.py` - запуск только web-режима
- `config.py` - чтение `.env`
- `db.py` - БД, миграции, запросы
- `handlers/` - логика Telegram-бота
- `web/` - фронтенд (`index.html`, `vote.html`, `admin.html`)

## 9) Тестовое наполнение песнями
```bash
python3 seed.py --force
```
Список песен меняется в `seed.py` (`SEED_SONGS`).

## 10) systemd (если уже настроен на сервере)
```bash
systemctl status juri-bot
systemctl restart juri-bot
journalctl -u juri-bot -f
```

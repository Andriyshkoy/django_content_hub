# ContentHub

Готовый проект контент‑хаба на **Django + DRF** с инфраструктурой в **Docker Compose** (PostgreSQL + Redis + Celery worker + Celery beat + Nginx),
агрегацией просмотров в Redis и периодическим сбросом в БД, преднастроенными `settings`, `pre-commit`, `Makefile` и Health‑check.

## Содержание

1. Возможности
2. Архитектура
3. Модели данных
4. API
5. Счетчики просмотров (Redis + Celery)
6. Админка
7. Установка и запуск
8. Переменные окружения
9. Полезные команды
10. Тесты и фикстуры
11. Продакшн‑заметки
12. Расширение проекта
13. Структура репозитория

## 1) Возможности

- Django 5 + DRF: быстрый REST API со страницами и вложенным контентом.
- Контентные типы: видео и аудио из коробки; легко расширить.
- Генерик‑связь страницы с произвольным контентом через `GenericForeignKey`.
- Счетчики просмотров: буферизация инкрементов в Redis, фоновый сброс в БД.
- Celery worker + beat: надежная обработка задач, перезапуск при падениях.
- Docker Compose: web, nginx, db, redis, worker, beat.
- Админка с inline‑редактором и кросс‑модельным автокомплитом контента.
- Преднастройки: CORS (dev), пагинация DRF, health‑check, pre‑commit хуки.

## 2) Архитектура

- Web (Gunicorn + Django) обслуживается Nginx’ом, статические файлы раздаются из тома.
- PostgreSQL — основная БД (в тестах/локально по умолчанию может использоваться SQLite).
- Redis — брокер Celery и отдельная БД/инстанс для буфера счетчиков.
- Celery worker — очереди `celery` и `batch` (для сброса счетчиков).
- Celery beat — периодический запуск задач, в том числе `flush_impressions`.

## 3) Модели данных

- `Page` — страница.
- `ContentBase` — базовый абстрактный класс с `title` и `counter`.
- `VideoContent` — `file_url`, `subtitles_url`.
- `AudioContent` — `text`.
- `PageContent` — связь `Page` ↔ контент с `GenericForeignKey`.

## 4) API

Базовый префикс: `/api/v1/` (версионирование URL, текущая версия — v1).

- `GET /api/v1/pages/` — список страниц (DRF PageNumberPagination), поля: `id`, `title`, `url`.
- `GET /api/v1/pages/{id}/` — детальная страница c массивом `contents`.
  - Элементы `contents` гомогенизируются по типу:
    - video: `id`, `type="video"`, `title`, `counter`, `file_url`, `subtitles_url`.
    - audio: `id`, `type="audio"`, `title`, `counter`, `text`.
- `GET /health/` — health‑check (`{"status":"ok"}`).

Документация OpenAPI (drf-spectacular):

- Схема: `GET /api/schema/` (JSON/YAML)
- Swagger UI: `GET /api/docs/`
- ReDoc: `GET /api/redoc/`

Примечание: при открытии `detail` эндпоинта инкременты просмотров контента откладываются в Celery и не блокируют ответ API.

## 5) Счетчики просмотров (Redis + Celery)

Пайплайн:

1. `PageViewSet.retrieve` группирует ID объектов контента по Django‑лейблу модели и публикует задачу `ingest_impressions(label, ids)`.
2. `ingest_impressions` в рабочем режиме суммирует инкременты в Redis Hash `views:counter:{label}` и отмечает активные лейблы в `views:labels`.
   - Идемпотентность по Celery `task_id` через ключ `views:dedup:{id}` с TTL.
   - В режиме тестов/`CELERY_TASK_ALWAYS_EAGER` — прямое обновление в БД, чтобы тесты не зависели от Redis.
3. `flush_impressions` (каждую секунду через Celery beat) для каждого лейбла:
   - атомарно переименовывает ключ в временный (`RENAME`),
   - читает его батчами (`HSCAN`) и
   - применяет инкременты к БД:
     - PostgreSQL: одним `UPDATE ... FROM (VALUES ...)` на батч,
     - Иные БД: через `F("counter") + delta`.

## 6) Админка

- `Page` с inline `PageContent`.
- Выбор контента — единый выпадающий список с автокомплитом по всем разрешенным моделям.
- Формат значения: `app_label.model_name:pk` (например, `pages.videocontent:42`).
- Набор разрешенных моделей:
  - через `settings.PAGES_ALLOWED_CONTENT_MODELS = ["app.Model", ...]`, либо
  - автообнаружение всех неабстрактных подклассов `ContentBase` среди установленных приложений.

## 7) Установка и запуск

### 7.1 Docker (рекомендуется)

1) Скопируйте переменные окружения:
```bash
cp .env.example .env
```
2) Поднимите сервисы:
```bash
docker compose up -d --build
```
3) Примените миграции и создайте суперпользователя:
```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```
4) Проверьте:
- API health‑check: http://localhost/health/
- Админка: http://localhost/admin/

Сервисы и тома описаны в `docker-compose.yaml`.

### 7.2 Локально (без Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Для локального Redis без Docker укажите локальный URL:
# COUNTER_REDIS_URL=redis://localhost:6379/1
# CELERY_BROKER_URL=redis://localhost:6379/0
python manage.py migrate
python manage.py runserver
```

Отдельно запустите Celery:

```bash
celery -A config worker -l info -Q celery,batch
celery -A config beat -l info
```

## 8) Переменные окружения

Основные (`.env`):

- Django: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_TIME_ZONE`.
- БД: `USE_POSTGRES`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`.
- Redis/Celery: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`.
- Счетчики: `COUNTER_REDIS_URL` (отдельная БД/инстанс Redis), `COUNTER_DEDUP_TTL` (сек.).
- (Опционально) Админ‑фильтрация: `PAGES_ALLOWED_CONTENT_MODELS`.

## 9) Полезные команды (Makefile)

```bash
make up          # поднять контейнеры
make logs        # логи сервисов
make down        # остановить и удалить
make migrate     # миграции
make superuser   # создать суперпользователя
make shell       # Django shell
make test        # pytest
```

## 10) Тесты и фикстуры

- Запуск тестов (в Docker): `make test`.
- Пример данных: `python manage.py loaddata pages/fixtures/sample_content.json`.

## 11) Продакшн‑заметки

- CORS: по умолчанию разрешены все источники (dev‑режим). Для прод ограничьте `CORS_ALLOWED_ORIGINS`.
- Секреты и креды — всегда через секрет‑хранилище/CI, не коммитьте реальные `.env`.
- Тайминг `flush_impressions` и `batch_size` подберите по нагрузке.
- Мониторинг: метрики Celery/Redis/DB и логи Nginx.

## 12) Расширение проекта

Добавление нового типа контента:

1. Создайте модель на базе `ContentBase`.
2. Добавьте сериализатор и зарегистрируйте его в `CONTENT_SERIALIZER_MAP`.
3. (Опционально) Добавьте в `PAGES_ALLOWED_CONTENT_MODELS` или положитесь на автообнаружение.
4. Зарегистрируйте модель в админке.

## 13) Структура репозитория

- `docker-compose.yaml` — Docker Compose (web, nginx, db, redis, worker, beat)
- `Dockerfile` — образ приложения
- `requirements.txt` — зависимости (Django, DRF, Celery и пр.)
- `config/` — Django‑проект (настройки, URL’ы, Celery‑инициализация)
- `pages/` — модели, сериализаторы, вьюхи, задачи, админка, формы, тесты
- `Makefile`, `.pre-commit-config.yaml`, `.flake8` — инструменты разработки
- `.env.example` — пример переменных окружения

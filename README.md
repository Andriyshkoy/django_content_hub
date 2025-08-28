# ContentHub

Быстрый каркас для тестового проекта на **Django + DRF** с Docker Compose (Postgres + Redis),
фоновой обработкой задач через **Celery**, преднастроенными `settings`, `pre-commit`, `Makefile` и Health-check endpoint.

## Быстрый старт (Docker)

1) Скопируйте переменные окружения:
```bash
cp .env.example .env
```
2) Поднимите сервисы:
```bash
docker compose up -d --build
```
3) Примените миграции и создайте суперпользователя (интерактивно):
```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```
4) Проверьте:
- API health-check: http://localhost:8000/health/  → `{"status":"ok"}`
- Админка: http://localhost:8000/admin/

## Структура
- `compose.yaml` — Docker Compose (web, worker, db, redis)
- `Dockerfile` — образ приложения
- `requirements.txt` — зависимости (Django, DRF, Celery и пр.)
- `config/` — Django-проект
  - `settings.py` — чтение `.env`, Postgres/Redis, DRF-пагинация
  - `urls.py` — админка и `/health/`
- `Makefile` — полезные команды для разработки
- `.pre-commit-config.yaml` — форматирование и линт
- `.env.example` — пример переменных окружения

## Полезные команды (локально)
```bash
make up          # поднять контейнеры
make logs        # логи
make down        # остановить и удалить
make migrate     # миграции
make superuser   # создать суперпользователя
make shell       # Django shell
make test        # запустить pytest
```

## API

- `GET /api/pages/` — список страниц с пагинацией.
- `GET /api/pages/{id}/` — детальная информация о странице с вложенным контентом. При обращении счётчики
  просмотров привязанных объектов увеличиваются в отдельной Celery-задаче.

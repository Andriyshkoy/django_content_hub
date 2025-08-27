.PHONY: up down logs build shell migrate superuser makemigrations test

up:
    docker compose up -d --build

down:
    docker compose down -v

logs:
    docker compose logs -f --tail=200

build:
    docker compose build web

shell:
    docker compose exec web python manage.py shell

migrate:
    docker compose exec web python manage.py migrate

makemigrations:
    docker compose exec web python manage.py makemigrations

superuser:
    docker compose exec web python manage.py createsuperuser

test:
    docker compose exec web python manage.py test -v 2
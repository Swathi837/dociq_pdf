.PHONY: up down logs shell-backend shell-db migrate reset

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f backend celery_worker

build:
	docker-compose build --no-cache

shell-backend:
	docker exec -it dociq_backend bash

shell-db:
	docker exec -it dociq_db psql -U dociq -d dociq

migrate:
	docker exec -it dociq_backend alembic upgrade head

migration:
	docker exec -it dociq_backend alembic revision --autogenerate -m "$(name)"

reset:
	docker-compose down -v
	docker-compose up -d

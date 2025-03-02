.PHONY: build up down logs shell migrate makemigrations collectstatic createsuperuser test test-cov clean tailwind-install tailwind-start tailwind-build tailwind-watch

# Docker-compose commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

# Django commands
shell:
	docker-compose exec web python manage.py shell

migrations:
	docker-compose exec web python manage.py makemigrations

migrate:
	docker-compose exec web python manage.py migrate

collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

# Testing
test:
	docker-compose exec web pytest

test-cov:
	docker-compose exec web pytest --cov=. --cov-report=term

# Cleaning
clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

# Tailwind CSS commands
tailwind-install:
	poetry run python manage.py tailwind install

tailwind-start:
	poetry run python manage.py tailwind start

tailwind-build:
	poetry run python manage.py tailwind build

tailwind-watch:
	poetry run python manage.py tailwind watch

# Full deployment
deploy: build up migrate collectstatic tailwind-build
	@echo "Deployment complete!"

# Restart services
restart-web:
	docker-compose restart web

restart-worker:
	docker-compose restart celery_worker

restart-beat:
	docker-compose restart celery_beat
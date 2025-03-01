.PHONY: build up down logs shell migrate makemigrations collectstatic createsuperuser test clean

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
	docker-compose exec web python manage.py test

# Cleaning
clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

# Full deployment
deploy: build up migrate collectstatic
	@echo "Deployment complete!"

# Restart services
restart-web:
	docker-compose restart web

restart-worker:
	docker-compose restart celery_worker

restart-beat:
	docker-compose restart celery_beat
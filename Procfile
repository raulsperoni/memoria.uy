web: gunicorn memoria.wsgi:application --bind 0.0.0.0:$PORT
worker: celery -A memoria worker --loglevel=info
beat: celery -A memoria beat --loglevel=info

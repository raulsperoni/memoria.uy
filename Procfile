web: gunicorn memoria.wsgi:application --bind 0.0.0.0:$PORT
worker: celery -A memoria worker --loglevel=info

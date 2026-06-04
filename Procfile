web: gunicorn config.wsgi:application --workers 3 --bind 0.0.0.0:$PORT
worker: celery -A config worker -l info
beat: celery -A config beat -l info
release: python manage.py migrate --no-input

# Convenience targets. On Windows without `make`, run the underlying commands
# directly (see README) or use `python manage.py ...`.
PY ?= .venv/Scripts/python.exe   # on Linux/macOS: .venv/bin/python

.PHONY: install run migrate makemigrations superuser shell test cov lint fmt check up down

install:
	$(PY) -m pip install -r requirements/dev.txt

run:
	$(PY) manage.py runserver

migrate:
	$(PY) manage.py migrate

makemigrations:
	$(PY) manage.py makemigrations

superuser:
	$(PY) manage.py createsuperuser

shell:
	$(PY) manage.py shell

check:
	$(PY) manage.py check

test:
	$(PY) -m pytest

cov:
	$(PY) -m pytest --cov=apps --cov-report=term-missing

lint:
	$(PY) -m ruff check .

fmt:
	$(PY) -m ruff format .

up:
	docker compose up --build

down:
	docker compose down

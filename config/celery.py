"""Celery application.

Quotes refresh, portfolio recalculation and digests run here from Stage 2 on.
The broker/result backend are read from Django settings (CELERY_* namespace).
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("freemium")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:  # pragma: no cover - sanity helper
    print(f"Request: {self.request!r}")

"""Development settings."""
import time

from .base import *  # noqa: F401,F403
from .base import (
    BASE_DIR,  # noqa: F401
    env,
)

DEBUG = True

# Bust the browser's CSS/JS cache on every server start so edits show up without
# a manual hard-refresh (prod hashes filenames via WhiteNoise instead).
STATIC_VERSION = str(int(time.time()))

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Email in dev:
#   - If EMAIL_HOST is set (e.g. a Gmail app password in .env), send for real.
#   - Otherwise write each message to a file under sent_emails/ so the password
#     reset / verification link is easy to open locally (the console backend
#     buries it in server logs and is easy to miss).
if env("EMAIL_HOST", default=""):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
    DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@freemium.app")
else:
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = BASE_DIR / "sent_emails"

# Run Celery tasks synchronously in dev unless a worker is explicitly wired up.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=True)
CELERY_TASK_EAGER_PROPAGATES = True

INTERNAL_IPS = ["127.0.0.1"]

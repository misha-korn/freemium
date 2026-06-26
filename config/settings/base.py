"""Base settings shared by all environments.

Environment-specific overrides live in ``dev.py`` and ``prod.py``.
Secrets and environment-dependent values are read from the environment
(optionally via a ``.env`` file) using ``django-environ`` — never hardcode them.
"""
from pathlib import Path

import environ
from celery.schedules import crontab
from django.utils.translation import gettext_lazy as _

# BASE_DIR -> project root (the directory that contains manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
)

# Load a .env file if present (local dev). In prod, real env vars take over.
environ.Env.read_env(BASE_DIR / ".env")

# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-CHANGE-ME-in-env")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "allauth",
    "allauth.account",
]

# Local apps. Each lives under the ``apps/`` package; the default app label is
# the last path component (e.g. ``apps.accounts`` -> label ``accounts``).
LOCAL_APPS = [
    "apps.accounts",
    "apps.portfolio",
    "apps.marketdata",
    "apps.analytics",
    "apps.billing",
    "apps.notifications",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# --------------------------------------------------------------------------- #
# Middleware
# --------------------------------------------------------------------------- #
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # LocaleMiddleware sits after Session (reads the language cookie/session) and
    # before Common (which may redirect based on the active locale).
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # allauth must come after AuthenticationMiddleware
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Exposes LANGUAGES / LANGUAGE_CODE to templates for the switcher.
                "django.template.context_processors.i18n",
                # Cache-busting version for CSS/JS query strings.
                "config.context_processors.static_version",
                # Unread-notification count for the nav badge.
                "config.context_processors.notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
# Reads DATABASE_URL (e.g. postgres://user:pass@host:5432/db). An empty OR unset
# value falls back to a local SQLite file so a fresh clone runs without Postgres;
# production must set DATABASE_URL to PostgreSQL (financial data + window funcs).
# NB: env.db() parses an empty string into the dummy backend, so guard for it.
DATABASE_URL = env("DATABASE_URL", default="").strip()
if DATABASE_URL:
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }
    }

# --------------------------------------------------------------------------- #
# Authentication / allauth
# --------------------------------------------------------------------------- #
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "/portfolio/"
LOGOUT_REDIRECT_URL = "/"

# allauth 65.x style configuration
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_UNIQUE_EMAIL = True
# Custom allauth forms: clearer login-field label + no always-on password rules.
ACCOUNT_FORMS = {
    "login": "apps.accounts.forms.LoginForm",
    "signup": "apps.accounts.forms.SignupForm",
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------- #
# Internationalization
# --------------------------------------------------------------------------- #
LANGUAGE_CODE = "en"

# Languages offered in the UI switcher. `en` is the source language; ru/es/zh-hans
# ship translated catalogs under locale/<code>/LC_MESSAGES/.
LANGUAGES = [
    ("en", _("English")),
    ("ru", _("Russian")),
    ("es", _("Spanish")),
    ("zh-hans", _("Simplified Chinese")),
    ("fr", _("French")),
    ("de", _("German")),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = env("DJANGO_TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------- #
# Static & media
# --------------------------------------------------------------------------- #
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Cache-busting token appended to CSS/JS URLs (see config.context_processors).
# Overridden per-environment: dev bumps it on every server start.
STATIC_VERSION = env("STATIC_VERSION", default="1")

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# Money / Decimal policy (project-wide convention)
# --------------------------------------------------------------------------- #
# All monetary amounts use DecimalField — never FloatField. These constants are
# the shared precision used across portfolio/marketdata/analytics.
MONEY_MAX_DIGITS = 20
MONEY_DECIMAL_PLACES = 8  # enough for crypto/FX; display rounds per currency

# --------------------------------------------------------------------------- #
# Django REST Framework
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

# --------------------------------------------------------------------------- #
# Celery (broker/backend wired in Stage 2; safe defaults here)
# --------------------------------------------------------------------------- #
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_TASK_TIME_LIMIT = 60 * 10
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 8
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Periodic price refresh (Celery Beat). Interval in seconds; default 15 min.
# Run a beat process alongside the worker: ``celery -A config beat -l info``.
MARKETDATA_REFRESH_SECONDS = env.int("MARKETDATA_REFRESH_SECONDS", default=15 * 60)
CELERY_BEAT_SCHEDULE = {
    "refresh-active-quotes": {
        "task": "apps.marketdata.tasks.refresh_active_quotes",
        "schedule": float(MARKETDATA_REFRESH_SECONDS),
    },
    # Daily portfolio digest (in-app + email for opted-in users).
    "daily-portfolio-digest": {
        "task": "apps.notifications.tasks.send_daily_digest",
        "schedule": crontab(hour=8, minute=0),
    },
    # Daily mark-to-market value snapshot (value-over-time chart).
    "daily-portfolio-snapshot": {
        "task": "apps.portfolio.tasks.snapshot_portfolios",
        "schedule": crontab(hour=23, minute=30),
    },
}

# --------------------------------------------------------------------------- #
# Cache (Redis in non-dev; locmem fallback)
# --------------------------------------------------------------------------- #
REDIS_URL = env("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

# --------------------------------------------------------------------------- #
# Market-data providers (used from Stage 2)
# --------------------------------------------------------------------------- #
# MOEX ISS needs no key. International providers do — read from env, default "".
FINNHUB_API_KEY = env("FINNHUB_API_KEY", default="")
ALPHA_VANTAGE_API_KEY = env("ALPHA_VANTAGE_API_KEY", default="")
TWELVE_DATA_API_KEY = env("TWELVE_DATA_API_KEY", default="")

# Static FX rates ({from: {to: rate}}) used to aggregate multi-currency
# portfolios into a single base currency. A deliberate Stage 2 stop-gap: a live
# FX provider replaces this later (see apps.marketdata.fx). Same-currency
# portfolios need no rates. Example: {"USD": {"RUB": "90"}, "EUR": {"USD": "1.08"}}
FX_RATES: dict[str, dict[str, str]] = {}

# --------------------------------------------------------------------------- #
# Billing / subscriptions (Stage 4)
# --------------------------------------------------------------------------- #
# Active payment provider: "dev" simulates checkout/webhooks for local testing
# (no keys, no real money); swap to "yookassa"/"stripe" once keys are set.
BILLING_PROVIDER = env("BILLING_PROVIDER", default="dev")
# Master switch for paid checkout. Default False: until a real provider
# (YooKassa/Stripe) is wired with keys, the "Upgrade to Pro" CTA shows a
# "coming soon" state instead of a broken checkout. Flip to True to sell again —
# nothing about the plan or feature gating is removed, only the buy button.
BILLING_ENABLED = env.bool("BILLING_ENABLED", default=False)
# Pro plan price + billing period. DecimalField/Decimal elsewhere — string here.
PRO_PRICE_AMOUNT = env("PRO_PRICE_AMOUNT", default="499")
PRO_PRICE_CURRENCY = env("PRO_PRICE_CURRENCY", default="RUB")
PRO_PERIOD_DAYS = env.int("PRO_PERIOD_DAYS", default=30)
# Free-plan limits (Pro lifts these). None elsewhere means "unlimited".
FREE_MAX_PORTFOLIOS = env.int("FREE_MAX_PORTFOLIOS", default=1)
# Shared secret used to sign/verify webhooks (HMAC). Required in prod.
BILLING_WEBHOOK_SECRET = env("BILLING_WEBHOOK_SECRET", default="dev-webhook-secret")
# YooKassa (RU payments). Set both to go live with BILLING_PROVIDER=yookassa +
# BILLING_ENABLED=True. Empty by default — the dev provider stays in charge.
YOOKASSA_SHOP_ID = env("YOOKASSA_SHOP_ID", default="")
YOOKASSA_SECRET_KEY = env("YOOKASSA_SECRET_KEY", default="")

# --------------------------------------------------------------------------- #
# Notifications (Stage 5)
# --------------------------------------------------------------------------- #
# Telegram Bot API token for digest/alert delivery. Empty -> Telegram disabled
# (in-app + email still work); set a real bot token to enable.
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

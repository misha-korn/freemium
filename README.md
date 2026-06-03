# Freemium — personal investment / portfolio tracker

A B2C investment tracker built with Django. Log your trades by hand, see your
positions and cost basis per portfolio, and (from Stage 2) pull live quotes
from **MOEX** and **international** markets for real returns, allocation and
risk. Monetised as **freemium**: a useful Free tier plus a paid **Pro**
subscription.

> **Status: Stage 1 (Foundation) complete.** Custom user + auth, portfolios,
> assets, manual transactions, computed positions, and the app skeleton for
> market data, analytics, billing and notifications. 33 tests, ~85% coverage.

---

## Tech stack

| Layer | Choice |
|------|--------|
| Backend | Django 5.2 + Django REST Framework |
| Auth | django-allauth (custom `User` from day one) |
| Database | PostgreSQL (SQLite fallback for quick local dev) |
| Background tasks | Celery + Redis *(wired in Stage 2)* |
| Cache | Redis (LocMem fallback) |
| Payments | YooKassa / CloudPayments / Stripe *(Stage 4)* |
| Deploy | Docker + Gunicorn + WhiteNoise |
| Monitoring | Sentry *(prod)* |

**Money rule:** every monetary value is a `DecimalField` — **never** `FloatField`.

## Project layout

```
config/                 # project package
  settings/             # split settings: base / dev / prod
  urls.py, celery.py, wsgi.py, asgi.py
apps/
  accounts/             # custom User, Subscription, profile, allauth templates
  portfolio/            # Portfolio, Asset, Transaction + position services (core)
  marketdata/           # PriceQuote + quote provider abstraction (MOEX + intl)
  analytics/            # pure service layer: XIRR, allocation, returns
  billing/              # Payment, WebhookEvent + provider abstraction (stub)
  notifications/        # Notification + preferences (stub)
templates/              # base.html, home.html, shared partials
static/css/main.css     # design tokens + component system
docs/                   # ARCHITECTURE, DECISIONS, ROADMAP
```

## Quick start (Windows / PowerShell)

```powershell
# 1. Virtualenv + dependencies
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements\dev.txt

# 2. Environment
Copy-Item .env.example .env
# generate a secret key:
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
# paste it into .env as DJANGO_SECRET_KEY

# 3. Database + run
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/ . Sign up, create a portfolio, add an asset, log a trade.

On macOS/Linux use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.
A `Makefile` wraps the common commands (`make run`, `make test`, `make migrate`, …).

## Docker (Postgres + Redis + web + worker)

```bash
docker compose up --build
```

The `web` service runs migrations then `runserver`; `db` is Postgres and `redis`
is the broker/cache. Production builds use the Gunicorn `CMD` in the `Dockerfile`.

## Configuration

All environment-specific values come from the environment (or a local `.env`),
loaded by `django-environ`. See `.env.example` for the full list. Notable:

- `DATABASE_URL` — Postgres in prod; unset falls back to SQLite for dev.
- `DJANGO_SETTINGS_MODULE` — `config.settings.dev` (default) or `config.settings.prod`.
- `FINNHUB_API_KEY` — needed for international quotes (Stage 2). MOEX needs none.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=apps --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check apps config
```

## Roadmap

1. **Foundation** ✅ — auth, portfolios, assets, manual trades, positions.
2. **Quotes & analytics** — providers + Celery refresh, current value, returns, first chart.
3. **MVP dashboard** — allocation, performance, deploy.
4. **Monetisation** — Free/Pro limits, payments + webhooks.
5. **Retention** — tax report, Excel/PDF export, notifications, broker import.

See [docs/ROADMAP.md](docs/ROADMAP.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
and [docs/DECISIONS.md](docs/DECISIONS.md).

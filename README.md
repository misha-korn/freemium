# Freemium — personal investment / portfolio tracker

A B2C investment tracker built with Django. Log your trades by hand, see your
positions and cost basis per portfolio, and pull live quotes from **MOEX** and
**international** markets for real market value, returns (simple + XIRR) and an
invested-capital chart. Monetised as **freemium**: a useful Free tier plus a paid
**Pro** subscription.

> **Status: Stage 2 (Quotes & analytics) complete.** On top of Stage 1: live
> quotes persisted as `PriceQuote`, a Celery Beat periodic refresh (+ manual
> "Refresh prices"), mark-to-market valuation with unrealised P&L, simple +
> money-weighted (XIRR) returns, multi-currency aggregation via an FX converter,
> and a Chart.js portfolio chart. 69 tests, ~89% coverage, ruff-clean.

---

## Tech stack

| Layer | Choice |
|------|--------|
| Backend | Django 5.2 + Django REST Framework |
| Auth | django-allauth (custom `User` from day one) |
| Database | PostgreSQL (SQLite fallback for quick local dev) |
| Background tasks | Celery + Redis (periodic quote refresh) |
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

Open http://127.0.0.1:8000/ . Sign up, create a portfolio, add an asset, log a
trade, then hit **Refresh prices** on the portfolio to pull live quotes (MOEX
works with no API key) and see market value, returns and the chart.

On macOS/Linux use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.
A `Makefile` wraps the common commands (`make run`, `make test`, `make migrate`, …).

### Live quotes & periodic refresh (Stage 2)

In dev, `CELERY_TASK_ALWAYS_EAGER=True` (default) runs the refresh inline, so the
**Refresh prices** button works without any extra process. For the *periodic*
refresh, run a worker + beat against Redis:

```powershell
# set CELERY_TASK_ALWAYS_EAGER=False in .env, ensure Redis is running, then:
.\.venv\Scripts\python.exe -m celery -A config worker -l info
.\.venv\Scripts\python.exe -m celery -A config beat -l info
```

`refresh_active_quotes` runs every `MARKETDATA_REFRESH_SECONDS` (default 900).
Multi-currency portfolios need `FX_RATES` set in settings to show base-currency
totals; single-currency portfolios work out of the box.

## Docker (Postgres + Redis + web + worker)

```bash
docker compose up --build
```

The `web` service runs migrations then `runserver`; `db` is Postgres, `redis` is
the broker/cache, `worker` runs Celery and `beat` schedules the periodic quote
refresh. Production builds use the Gunicorn `CMD` in the `Dockerfile`.

## Configuration

All environment-specific values come from the environment (or a local `.env`),
loaded by `django-environ`. See `.env.example` for the full list. Notable:

- `DATABASE_URL` — Postgres in prod; unset falls back to SQLite for dev.
- `DJANGO_SETTINGS_MODULE` — `config.settings.dev` (default) or `config.settings.prod`.
- `FINNHUB_API_KEY` — needed for international quotes. MOEX needs none.
- `MARKETDATA_REFRESH_SECONDS` — periodic refresh interval for Celery Beat (default 900).
- `CELERY_TASK_ALWAYS_EAGER` — `True` in dev runs tasks inline (no worker needed).

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=apps --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check apps config
```

## Roadmap

1. **Foundation** ✅ — auth, portfolios, assets, manual trades, positions.
2. **Quotes & analytics** ✅ — providers + Celery refresh, market value, returns (simple + XIRR), FX, first chart.
3. **MVP dashboard** — allocation, performance, deploy.
4. **Monetisation** — Free/Pro limits, payments + webhooks.
5. **Retention** — tax report, Excel/PDF export, notifications, broker import.

See [docs/ROADMAP.md](docs/ROADMAP.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
and [docs/DECISIONS.md](docs/DECISIONS.md).

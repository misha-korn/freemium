# Freemium — personal investment / portfolio tracker

A B2C investment tracker built with Django. Log your trades by hand, see your
positions and cost basis per portfolio, and pull live quotes from **MOEX** and
**international** markets for real market value, returns (simple + XIRR) and an
invested-capital chart. Monetised as **freemium**: a useful Free tier plus a paid
**Pro** subscription.

> **Status: Stage 4 (Monetisation) complete.** Freemium plans are live: a
> `subscriptions` service with an enforced Free limit (1 portfolio) and unlimited
> Pro, a payment-provider abstraction with a **dev** provider that simulates
> checkout + HMAC-signed webhooks end-to-end (no keys, no real money), an
> upgrade → Pro → cancel flow, and a webhook that verifies the signature before
> activating Pro idempotently. Built on Stage 3 (allocation dashboard + deploy)
> and Stage 3.5 UX (branded auth, light/dark theme, i18n en/ru/es/zh-hans).
> 118 tests, ~92% coverage, ruff-clean. Honest by design — market-value basis
> only when fully priced, no fabricated sector, and no faked payment calls.

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

## Deploy (Stage 3)

### Render (one click, recommended)

`render.yaml` is a Blueprint describing the whole stack — **web** (Gunicorn),
**worker** + **beat** (Celery), managed **Postgres** and **Redis**:

1. Push this repo to GitHub.
2. On Render: **New + → Blueprint**, pick the repo. Render reads `render.yaml`.
3. Apply. `DJANGO_SECRET_KEY` is generated; `DATABASE_URL` / `REDIS_URL` /
   `CELERY_*` are wired automatically.

On deploy the web service runs `collectstatic` (build) and `migrate`
(pre-deploy). The Render hostname is trusted automatically (`prod.py` reads
`RENDER_EXTERNAL_HOSTNAME`), so it serves immediately; add any custom domain to
`DJANGO_ALLOWED_HOSTS`. Free Redis/Postgres are fine to start; the free web
instance sleeps when idle.

### VPS / Docker

Build the image (`Dockerfile`, Gunicorn `CMD`) and run `bin/release.sh`
(`migrate` + `collectstatic`) as your deploy hook before starting the web
process; run `worker` and `beat` from the same image (see the `Procfile` for the
exact process commands). Provide `DJANGO_SETTINGS_MODULE=config.settings.prod`,
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL` and the
`CELERY_*` URLs via the environment.

## Configuration

All environment-specific values come from the environment (or a local `.env`),
loaded by `django-environ`. See `.env.example` for the full list. Notable:

- `DATABASE_URL` — Postgres in prod; unset falls back to SQLite for dev.
- `DJANGO_SETTINGS_MODULE` — `config.settings.dev` (default) or `config.settings.prod`.
- `FINNHUB_API_KEY` — needed for international quotes. MOEX needs none.
- `MARKETDATA_REFRESH_SECONDS` — periodic refresh interval for Celery Beat (default 900).
- `CELERY_TASK_ALWAYS_EAGER` — `True` in dev runs tasks inline (no worker needed).
- `BILLING_PROVIDER` — `dev` (simulated, default) or `yookassa`/`stripe` once keys exist.
- `PRO_PRICE_AMOUNT` / `PRO_PRICE_CURRENCY` / `PRO_PERIOD_DAYS` — Pro plan price and period.
- `FREE_MAX_PORTFOLIOS` — Free-plan portfolio cap (default 1; Pro is unlimited).
- `BILLING_WEBHOOK_SECRET` — HMAC secret to sign/verify webhooks (set a strong value in prod).

## Internationalisation & theming

The UI ships in **English, Russian, Spanish and Simplified Chinese**, switchable
from the header (cookie/session based via `LocaleMiddleware` + `set_language`).
A light/dark theme toggle sits next to it — a no-flash inline script applies the
saved or OS-preferred theme before first paint, and the choice persists in
`localStorage`.

Translations are managed **without GNU gettext** (rarely present on Windows):
strings live in `bin/build_translations.py`, which writes
`locale/<code>/LC_MESSAGES/django.{po,mo}` with `polib`. To add or change a string:

```powershell
# 1. wrap it in {% trans %}/{% blocktrans trimmed %} (templates) or _() (Python)
# 2. add its msgid + translations to bin/build_translations.py
.\.venv\Scripts\python.exe -m pip install polib
.\.venv\Scripts\python.exe bin\build_translations.py   # regenerates .po + .mo
```

The compiled `.mo` files are committed, so deploys need no gettext. (If you *do*
have gettext, the standard `makemessages`/`compilemessages` also work.)

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=apps --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check apps config
```

## Roadmap

1. **Foundation** ✅ — auth, portfolios, assets, manual trades, positions.
2. **Quotes & analytics** ✅ — providers + Celery refresh, market value, returns (simple + XIRR), FX, first chart.
3. **MVP dashboard** ✅ — allocation donuts, account overview, Render/VPS deploy.
   - **3.5 UX** ✅ — branded auth pages, light/dark theme, i18n (en/ru/es/zh-hans).
4. **Monetisation** ✅ — Free/Pro plans, enforced limits, dev payment provider, verified webhooks.
5. **Retention** — tax report, Excel/PDF export, notifications, broker import.

See [docs/ROADMAP.md](docs/ROADMAP.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
and [docs/DECISIONS.md](docs/DECISIONS.md).

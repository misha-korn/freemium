# Architecture

Freemium follows Django's "many small apps + a service layer" approach. Each app
owns one domain; cross-cutting calculations live in service modules (not in
views or models) so they are pure and testable.

## Apps

| App | Responsibility | Key objects |
|-----|----------------|-------------|
| `accounts` | Identity & subscription state | `User` (custom), `Subscription`, signals, profile views, allauth templates |
| `portfolio` | Core product | `Portfolio`, `Asset`, `Transaction`, `services.compute_positions/portfolio_summary` |
| `marketdata` | Quotes & FX | `PriceQuote`, `providers/` abstraction, `services` (cache + persist + `latest_quotes`), `fx` converter, Celery `refresh_*` tasks |
| `analytics` | Calculations | pure `services`: `xirr`, `allocation_by`, `simple_return` (no models) |
| `portfolio.valuation` | Mark-to-market | `value_positions` (pure), `portfolio_valuation`, `invested_timeseries` |
| `billing` | Payments | `Payment`, `WebhookEvent`, `PaymentProvider` interface, pricing + webhook views |
| `notifications` | Messaging | `Notification`, `NotificationPreference`, `notify()`, digest task |

## Data model (Stage 1)

```
User 1───1 Subscription
User 1───* Portfolio 1───* Transaction *───1 Asset
Asset 1───* PriceQuote            (marketdata)
User 1───* Payment                (billing)
WebhookEvent  (idempotency: unique provider+event_id)
User 1───* Notification ; User 1───1 NotificationPreference
```

- **Holdings are computed, not stored.** `portfolio.services.compute_positions`
  replays a portfolio's transactions (average-cost method) to produce current
  positions. This keeps trades as the single source of truth. It can be
  denormalised later if profiling demands it.
- **Money** is always `Decimal`. Amounts use `DecimalField(max_digits=20,
  decimal_places=8)`, quantities `max_digits=24` (crypto micro-units).

## Market-data provider abstraction

`marketdata/providers/` defines a single `QuoteProvider` interface returning an
immutable `Quote`. `registry.get_provider(market)` maps a market code to a
concrete provider:

- `MOEX` → `MoexQuoteProvider` (public MOEX ISS API, no key, RUB).
- `US` / `EU` / `GLOBAL` → `FinnhubQuoteProvider` (needs `FINNHUB_API_KEY`).
- anything else → `NullQuoteProvider` (safe no-op).

`services.get_cached_quote` adds Django-cache memoisation. `fetch_and_store_quote`
persists a `PriceQuote`; `latest_quotes(asset_ids)` reads the newest row per asset
(portable — no Postgres `DISTINCT ON`).

## Quote refresh (Stage 2)

`refresh_active_quotes` (Celery Beat, every `MARKETDATA_REFRESH_SECONDS`, default
15 min) finds every asset referenced by a transaction and fans out one
`refresh_quote` subtask each, so a slow/failing provider on one asset never blocks
the rest. A POST-only "Refresh prices" button on the portfolio detail enqueues the
same per-asset refresh on demand (inline under `CELERY_TASK_ALWAYS_EAGER` in dev).

## Valuation & FX (Stage 2)

`portfolio.valuation.portfolio_valuation` ties it together: replay positions →
`latest_quotes` → `value_positions` (pure: market value, unrealised P&L, simple
return per position, in the asset's own currency) → aggregate per-currency and,
via `marketdata.fx`, into the base currency. `_portfolio_xirr` builds dated,
base-currency cashflows (buys negative, sells/terminal value positive) and calls
`analytics.xirr`. Anything that cannot be priced or converted is reported as
`None` / listed in `missing_prices` / `missing_fx` — never fabricated.

`invested_timeseries` powers the first chart: cumulative net invested capital over
time (Chart.js), which needs no historical prices.

## Dashboard & allocation (Stage 3)

`portfolio.allocation.build_allocation` is pure: it takes the `ValuedPosition`
list `portfolio_valuation` already produced and groups base-currency value across
four axes — **holding** (ticker), **asset class** (`asset_type`), **market** and
**currency** — reusing `analytics.allocation_by` for the weights. Basis is market
value when every position is priced, else invested capital (labelled either way);
unconvertible currencies are excluded and reported in `missing_fx`. `chart_payload`
shapes a breakdown for Chart.js (labels + float percentages — chart-only; money
stays Decimal). `PortfolioDetailView` renders one donut per axis that has more
than one slice (`static/js/allocation_charts.js`).

`portfolio.overview.build_account_overview` powers the portfolio list: one
`PortfolioCard` per portfolio (its own base-currency totals) plus a combined total
*only* when every portfolio shares one currency — never summed across currencies
without FX.

Industry sector is deliberately absent — `Asset` has no sector field and no
provider supplies one, so it would be fabricated. See `docs/DECISIONS.md`.

## Request → response flow (example: add a trade)

1. `POST /portfolio/<pk>/transactions/new/` → `TransactionCreateView`.
2. View confirms `request.user` owns the portfolio (404 otherwise).
3. `TransactionForm` validates (quantity > 0, price ≥ 0).
4. On success the `Transaction` is saved and the user is redirected to the
   portfolio detail, where `compute_positions` recalculates holdings.

## Settings & deployment

Split settings (`base` / `dev` / `prod`). Secrets come from the environment via
`django-environ`. Production enables HSTS, secure cookies, SSL redirect,
WhiteNoise compressed/hashed static, and optional Sentry. Gunicorn serves WSGI.

Stage 3 adds deploy artifacts: `render.yaml` (a Render Blueprint provisioning
web + worker + beat + Postgres + Redis), a `Procfile` and `bin/release.sh`
(`migrate` + `collectstatic`) for VPS/Docker, and `.gitattributes` pinning
shell/manifest files to LF. `prod.py` trusts `RENDER_EXTERNAL_HOSTNAME`
(auto-set by Render) for `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`, so a fresh
deploy serves before any host is configured by hand.

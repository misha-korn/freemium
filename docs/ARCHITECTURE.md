# Architecture

Freemium follows Django's "many small apps + a service layer" approach. Each app
owns one domain; cross-cutting calculations live in service modules (not in
views or models) so they are pure and testable.

## Apps

| App | Responsibility | Key objects |
|-----|----------------|-------------|
| `accounts` | Identity & subscription state | `User` (custom), `Subscription`, signals, profile views, allauth templates |
| `portfolio` | Core product | `Portfolio`, `Asset`, `Transaction`, `services.compute_positions/portfolio_summary` |
| `marketdata` | Quotes | `PriceQuote`, `providers/` abstraction, `services.get_cached_quote`, Celery tasks |
| `analytics` | Calculations | pure `services`: `xirr`, `allocation_by`, `simple_return` (no models) |
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

`services.get_cached_quote` adds Django-cache memoisation. Stage 2 adds Celery
periodic refresh that persists `PriceQuote` rows.

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

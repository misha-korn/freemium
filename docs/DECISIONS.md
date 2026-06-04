# Key decisions (ADR-lite)

### Custom `User` from day one
Subclassed `AbstractUser` before the first migration. Swapping the user model
later is painful; doing it now is free and lets us extend identity safely.

### Money is always `Decimal`, never `float`
Floats introduce rounding errors that are unacceptable in finance. All amounts
are `DecimalField`; calculations use `decimal.Decimal`. Quantity fields allow 8
decimal places for crypto.

### Market scope = both (RU + international) via a provider abstraction
Rather than hardcode one data source, a `QuoteProvider` interface with a
`registry` lets MOEX and Finnhub (and future providers) coexist. A `NullProvider`
keeps unmapped markets safe.

### Manual entry first
Per the roadmap, broker API import is deferred. Stage 1 ships forms/CRUD for
portfolios, assets and trades — faster to a usable MVP and simpler to reason about.

### Holdings computed from transactions
Positions are derived (average-cost replay) instead of stored, keeping trades as
the single source of truth. Denormalise only if profiling requires it.

### Split settings + `apps/` package + service layer
`config.settings.{base,dev,prod}` separates concerns; all local apps live under
`apps/`; business logic lives in `services.py` modules (pure, testable) rather
than fattening views or models.

### Idempotent webhooks
`billing.WebhookEvent` has a unique `(provider, event_id)` constraint so repeated
provider deliveries are processed once. Signature verification + activation land
in Stage 4.

### Never fabricate a price or FX rate (Stage 2)
Valuation is honest by construction: a position with no usable quote is
`priced=False` and renders `—`; base-currency totals are produced only when every
involved currency converts, otherwise they are `None` and `missing_fx` names the
gaps. Per-currency figures stay exact regardless. This protects users from
confidently-wrong numbers — the cardinal sin in fintech.

### FX rates are a static stop-gap (Stage 2)
`marketdata.fx` resolves rates from `settings.FX_RATES` (identity for same
currency, `1/x` inverse otherwise). Single-currency portfolios — the common Free
case — need no configuration. A live FX feed can replace `_rate_table` later
without touching callers.

### First chart = invested capital, not mark-to-market (Stage 2)
A true value-over-time chart needs *historical* prices, which the current-quote
providers don't give us. Rather than back-date today's price onto past holdings
(dishonest), the first chart plots cumulative net invested capital from
transactions — fully honest and useful. Mark-to-market history (price backfill or
daily `PortfolioSnapshot`) is deferred.

### Fan-out quote refresh (Stage 2)
`refresh_active_quotes` dispatches one `refresh_quote` per held asset instead of
looping inline, so one slow/failing provider can't block the batch and retries
stay per-asset. Scheduled via Celery Beat (`MARKETDATA_REFRESH_SECONDS`).

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

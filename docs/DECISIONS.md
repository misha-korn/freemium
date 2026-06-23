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

### Allocation axes = real data, not a fabricated sector (Stage 3)
The roadmap lists "by asset / sector / currency", but `Asset` has no industry
*sector* and no provider feeds one yet. Rather than add an empty field that
renders as "Unclassified: 100%", allocation breaks down by the axes we *do* hold
honestly: **holding** (ticker), **asset class** (`asset_type`), **market** and
**currency**. Industry sector is deferred until a data source exists — consistent
with the "never fabricate" rule. A donut is drawn only for an axis with >1 slice,
so single-currency/single-market portfolios aren't cluttered with 100% pies.

### Allocation basis: market value when fully priced, else cost basis (Stage 3)
`build_allocation` weights slices on **market value** only when every position is
priced; otherwise it falls back to **invested capital** (always known, no quote
needed) and labels which basis it used. Positions whose currency can't convert to
the base are excluded and listed in `missing_fx` — never mixed in without a rate.

### Combined account total only within one currency (Stage 3)
The portfolio-list overview sums portfolios into one headline total *only* when
they all share a base currency; mixed-currency accounts show per-portfolio cards
but no combined figure (we don't sum across currencies without FX). Same honesty
rule as valuation, applied at the account level.

### Deploy via Render Blueprint + portable hooks (Stage 3)
`render.yaml` provisions web + worker + beat + Postgres + Redis in one click;
`prod.py` trusts `RENDER_EXTERNAL_HOSTNAME` so a fresh deploy serves immediately.
A `Procfile` and `bin/release.sh` (migrate + collectstatic) keep the same app
deployable on any VPS/PaaS. `.gitattributes` pins shell/manifest files to LF so
Linux hosts don't choke on CRLF.

### allauth templates live in project `templates/` (Stage 3.5)
Our branded `account/login.html`, `signup.html`, etc. were being shadowed by
allauth's own defaults: with `APP_DIRS=True`, Django returns the first match in
INSTALLED_APPS order, and `allauth.account` precedes `apps.accounts`. Moving them
to project-level `templates/account/` (the `DIRS` loader runs before app loaders)
makes our pages win. A regression test asserts the branded markers render.

### Theme: token-swap dark mode, no-flash, OS-aware (Stage 3.5)
Light/dark is a pure CSS custom-property swap under `[data-theme="dark"]` — every
component already reads tokens, so nothing per-component changes. An inline script
in `<head>` applies the saved/OS theme *before first paint* (no flash); `theme.js`
handles the toggle and persists to `localStorage`. Without JS the page still
renders (defaults to light).

### i18n without GNU gettext (Stage 3.5)
Windows dev boxes rarely have GNU gettext, so `makemessages`/`compilemessages`
fail. `bin/build_translations.py` is the stand-in: translations live in that file
and it writes `locale/<code>/LC_MESSAGES/django.{po,mo}` via `polib`. The compiled
`.mo` files are committed so runtime needs no gettext. Language is cookie/session
based via `LocaleMiddleware` + the `set_language` view (no `i18n_patterns`, so URLs
stay clean). `blocktrans` blocks use `trimmed` to keep msgids stable. Initial UI
languages: en (source), ru, es, zh-hans. Asset-class/market *data* labels and the
profile/CRUD forms are not yet translated — a follow-up.

### Subscription rules live in one service (Stage 4)
`billing.subscriptions` is the only place that activates/cancels Pro and answers
"what can this plan do" (`portfolio_limit`, `can_create_portfolio`). Views and the
webhook call it instead of mutating `Subscription` directly, so plan logic is
tested in isolation and a missing `Subscription` row safely reads as Free.

### Payment provider abstraction + dev provider (Stage 4)
Payments sit behind `billing.providers.PaymentProvider` (`create_checkout`,
`parse_webhook`). The **dev** provider drives the whole flow — checkout
"redirects" to an internal confirm page; webhooks are HMAC-signed exactly like a
real provider — so the production verify→activate path is exercised in tests with
no keys and no real money. YooKassa (RU) / Stripe register in the registry once
keys exist. The dev-confirm page 404s unless the dev provider is active, so it can
never become a free upgrade in production.

### Webhooks: verify signature before trusting the body (Stage 4)
The webhook computes the expected HMAC over the raw body and rejects (400) any
request whose signature is missing or wrong — *before* parsing or acting. Only
then does it deduplicate on `(provider, event_id)` and activate/cancel. An
already-processed event is acknowledged without re-acting. This is the cardinal
payments rule: never trust an unauthenticated webhook.

### Dividends: manual entry first, income per-currency, no fabricated yield (Stage 6)
Tier 1's #1 feature is dividends/coupons. A `DividendPayment` row stores one cash
event (`amount` gross, `tax_withheld`, `currency`, `paid_on`) — manual entry
first, matching the "manual before auto" stance; auto-pulling from MOEX ISS
(`/securities/{SECID}/dividends.json`) is the next increment. `net_amount` is
gross minus tax. The income summary and calendar group **per currency** and never
sum across currencies (same honesty rule as valuation/tax). **Yield-on-cost**
divides net income by the current open-position cost basis in that currency and is
`None` when no basis exists — we never invent a yield. Dividends are **free** for
all signed-in users (core value to drive adoption), unlike the Pro-gated tax
report. `paid_on` is a `DateField` (pay date drives history + calendar); ex-date
and per-share splits are deferred until the MOEX pull lands.

### Value over time: forward-only daily snapshots, stored only when priced (Stage 6)
The deferred mark-to-market chart needed *historical* prices the providers don't
give us. Rather than back-date today's price onto past holdings (dishonest), a
`PortfolioSnapshot` records one mark-to-market value per portfolio per day from
now on; the series accumulates forward. A snapshot is stored **only** when the
portfolio is fully priced and the base-currency total exists — partial/
unconvertible days are skipped, never persisted as a misleading value (same rule
as valuation). Because the free tier runs no Celery worker, snapshots are taken
both by a daily Beat task **and opportunistically** when a priced portfolio is
viewed; `update_or_create` on `(portfolio, as_of)` keeps one freshest row per day,
so the GET-time write is safe and idempotent. The value-vs-invested chart appears
once ≥2 snapshots exist; the invested-capital chart stays for day one. A benchmark
overlay (index level snapshotted in parallel, rebased to 100) is the next
increment — it needs an index data source.

### Free-plan gating by limit, not feature flags (Stage 4)
The enforced Free limit is `FREE_MAX_PORTFOLIOS` (default 1); Pro lifts it to
unlimited. The cap is checked in `PortfolioCreateView` for both GET (hide the
form) and POST (block creation), redirecting to pricing as an upsell. Other
"Pro" perks (exports, notifications) are advertised but not yet built — we gate
the one capability that exists rather than fake the rest.

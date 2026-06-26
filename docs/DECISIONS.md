# Key decisions (ADR-lite)

### YooKassa webhooks: verify by API re-fetch, not by signature (Stage 9)
Tier 4 wires real RU payments via `billing.providers.yookassa`. Unlike the dev
provider's HMAC, **YooKassa notifications are unsigned**, so `parse_webhook` does
not trust the body: it re-fetches the payment from the YooKassa API by id and
trusts the **API's** status. A spoofed notification therefore can't activate Pro,
because the API won't confirm a payment that didn't really succeed for our shop;
only an API-confirmed `succeeded` maps to an activating event. This slots into the
existing webhook view unchanged (verify → dedup on `(provider, event_id)` →
activate). Credentials are env-only (`YOOKASSA_SHOP_ID`/`_SECRET_KEY`), and the
whole thing stays **gated**: with no keys / `BILLING_ENABLED=False` the dev
provider stays in charge and the CTA shows "coming soon" — nothing collects money
until the owner flips it on and fills the offer's `[ФИО]`/`[ИНН]`.

### Public portfolios: opt-in, token-gated, composition-only (Stage 8)
Tier 3's #10 shares a portfolio via an **opt-in**, unguessable token link
(`secrets.token_urlsafe`) at `/p/<token>/`; `PublicPortfolioView` 404s unless
`is_public` is set, so a portfolio is never public by default and the link isn't
enumerable by id. The public page is **privacy-first**: a dedicated template
renders only the composition (allocation donuts + per-holding weights) and
returns (%) — never absolute amounts, the transaction history, or the owner's
username/email. Showing weights/returns rather than money lets a user share what
they hold without revealing their net worth. The owner toggles publish /
make-private on a Share page; making it private 404s the link again. (Regression
tests assert money and owner identity never appear on the public page.)

### Dividend forward estimate: labelled, cadence-inferred, never a fact (Stage 8)
With real dividend history imported, the income forecast adds a stock-dividend
**estimate** (`dividend_estimate`): infer the payout cadence from past ex-dates
(median gap snapped to monthly/quarterly/semi-annual/annual), then project the
latest per-share amount × shares forward over the horizon. Estimates require **≥2
real dividends** (one point can't fix a cadence — we don't guess) and are tagged
`estimate=True` so the forecast UI renders them as "(estimate)" beside the
*scheduled* bond coupons, with a footnote that real amounts/dates may differ.
Trailing-12-month dividends (a real figure) drive a per-currency yield-on-cost.
This keeps the strict "no fabricated facts" rule while still giving a useful
forward view — the estimate is clearly disclosed as such (user-approved).

### Stock dividend auto-import: real facts, two free-ish sources (Stage 8)
The "no data source" gap for stock dividends is closed for **history** first.
`marketdata.dividends` fetches real per-share dividends from **Twelve Data**
(international, `TWELVE_DATA_API_KEY`) and **MOEX ISS** (RU, no key), stored as
global `AssetDividend` rows (like `PriceQuote`). `portfolio.dividend_import`
records a `DividendPayment` per past dividend using the shares **actually held
before that ex-date** (as-recorded counts that match the provider's historical
per-share amount) — a real figure, not a guess. It covers assets ever traded (so
a dividend received while held but since sold is captured), is idempotent
(deduped on asset+ex-date), and runs from a "Pull from market" button (free tier
has no worker, so inline + cached 12h). The forward *estimate* + yield are a
separate next increment so the "facts" stay cleanly separated from any
projection. Twelve Data's free tier returns full history with a date range, so
cadence can be inferred there later.

### Income forecast projects only deterministic bond coupons (Stage 8)
Tier 3's #9 (dividend forecast / sectors / news) is gated on an external data
source. The honest slice shipped now is a **bond-coupon income forecast**
(`portfolio.forecast` + `bonds.upcoming_coupons`): a forward calendar of coupons
due in the next 12 months, computed deterministically from the user's
`BondDetail` (date + amount × quantity), per currency, grouped by month. Stock
dividends are **not** forecast — projecting them from history would fabricate
numbers, against the project's cardinal rule — and sector/news stay deferred
until a provider exists. A MOEX dividends endpoint could later power a real RU
stock-dividend forecast (needs live MOEX).

### PWA service worker is minimal and never caches data (Stage 8)
Tier 3's PWA (#8) makes the site installable with a web app manifest, generated
icons and a service worker. The worker is served from the **site root**
(`/sw.js`) so its scope covers the whole app, with `Service-Worker-Allowed: /`
and `Cache-Control: no-cache` so worker updates always propagate. It is
deliberately minimal: it precaches only an offline fallback page and intercepts
**only top-level navigations**, falling back to `/offline/` when the network is
down — it never caches portfolio data, which must always be fresh from the
server (caching stale balances would violate the honesty rule). The offline page
is self-contained (inline CSS) so it renders with nothing else cached. Manifest,
worker and offline page are served by `config.views` from root URLs.

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

### Corporate actions: splits adjust trade replay, cost basis preserved (Stage 7)
Tier 2 corporate actions (#7) handle stock splits. A `CorporateAction` stores the
ratio (new:old) + effective date; `portfolio.corporate_actions` replays each trade
executed **before** the split at quantity × factor and price ÷ factor (factor =
new ÷ old), so cost (quantity × price) is preserved while the share count and
average cost land in today's post-split terms. The same helper is applied in
`compute_positions`, the FIFO tax report and `held_quantity` so positions, realized
gains and the over-sell guard all agree on adjusted shares; with no splits it's a
no-op, leaving the common case (and all prior tests) unchanged. Splits are global
(on the shared `Asset`), edited from a per-portfolio Splits page scoped to traded
assets — consistent with how asset name / bond details are shared.

### Rebalancing: suggest only when priced; hold band; base-currency amounts (Stage 7)
Tier 2 rebalancing (#6) stores a `RebalanceTarget` (target weight % per asset) and
`portfolio.rebalance.build_rebalance` compares each holding's current weight
(market value converted to base) against it. Buy/sell **amounts are produced only
when the portfolio is fully priced and FX-convertible** (`available`); otherwise
targets stay editable but amounts render `—` — we never rebalance against
fabricated values. A 0.5%-of-portfolio **hold band** suppresses noise trades from
rounding, and targets for not-yet-held assets suggest a full buy. Suggestions are
in the base currency only (unit/lot rounding is left to the user). Targets are
edited inline on the Rebalance page (`target_<asset_id>` inputs); a blank removes
the target, and the view warns if targets exceed 100%.

### Bonds: manual reference data + derived coupon maths first (Stage 7)
Tier 2 bonds (#5) start with a `BondDetail` (OneToOne with a BOND `Asset`: face
value, coupon rate, frequency, maturity) and pure maths in `portfolio.bonds`.
Coupon dates are derived **backward from maturity** by the coupon period (the
standard assumption when the explicit schedule isn't known), so accrued coupon
(НКД) is a simple linear day-count between the surrounding coupon dates — no
issue date needed. We never invent a market price: an unpriced bond still renders
`—`, and the Bonds page shows reference figures (НКД, next coupon, days to
maturity), clearly labelled. Pricing from the MOEX bonds market (price as % of
face + `ACCRUEDINT`) is the next increment and needs live MOEX, so it's deferred
and verified on the user's machine — same stance as the quote providers.

### Broker import is tolerant + keyless, dispatched by file type (Stage 7)
Tier 2's broker import (#4) reuses the existing import page: an `.xlsx` upload is
parsed as a broker report, anything else as the strict CSV (dispatch on the file
extension in `ImportTradesView`). Broker layouts (Tinkoff/Sber) vary and carry
preamble/summary rows, so `portfolio.broker_import` is **tolerant** — it locates
the trades table by recognising the header from keywords (RU + EN), maps columns
by meaning, and skips rows it can't read (totals, blanks) rather than aborting
the file. Unknown tickers are **auto-created** with inferred fields (RUB → MOEX,
else GLOBAL; STOCK) so the user needn't pre-register holdings; no name/price
lookup happens during import to keep it offline and fast. It's shipped as
**beta** (validated against the documented structure + synthetic fixtures, not a
broad range of real exports) and the page invites the user to send a failing
file. Money stays Decimal; per-row errors are diagnostic English, like the CSV
import.

### Trade validation in the form, clamp stays as a guard (Stage 6)
Selling more than is held now fails validation in `TransactionForm.clean` with a
clear message ("you only hold N"), and selling with no position is blocked too —
instead of silently clamping the oversell to zero. The check uses
`services.held_quantity` (net BUYs − SELLs), and editing a SELL excludes itself
from the tally so a legitimate sell stays valid on edit. The view passes the
parent portfolio into the form because, on create, the instance has no portfolio
until `form_valid`. We deliberately **keep** the silent clamp in
`compute_positions`/`tax` as a defensive guard for any pre-existing/imported data
— the form is the user-facing gate, the clamp is the safety net. BUYs are never
restricted.

### Free-plan gating by limit, not feature flags (Stage 4)
The enforced Free limit is `FREE_MAX_PORTFOLIOS` (default 1); Pro lifts it to
unlimited. The cap is checked in `PortfolioCreateView` for both GET (hide the
form) and POST (block creation), redirecting to pricing as an upsell. Other
"Pro" perks (exports, notifications) are advertised but not yet built — we gate
the one capability that exists rather than fake the rest.

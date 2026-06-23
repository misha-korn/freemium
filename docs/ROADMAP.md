# Roadmap

## Stage 1 — Foundation ✅ (done)
- [x] Custom `User` (AbstractUser) + django-allauth (login/signup/logout/reset)
- [x] `Subscription` model + auto-create-on-signup signal
- [x] `Portfolio`, `Asset`, `Transaction` models (Decimal money)
- [x] Manual trade entry (CRUD), ownership-scoped views
- [x] Computed positions + cost basis (`services.compute_positions`)
- [x] App skeletons: marketdata (provider abstraction), analytics (XIRR), billing, notifications
- [x] Split settings, Docker, design system, 85% test coverage, ruff-clean

## Stage 2 — Quotes & analytics ✅ (done)
- [x] Wire Celery + Redis; periodic `refresh_active_quotes` (Celery Beat, 15-min default)
- [x] Persist `PriceQuote` (`marketdata.services.store/fetch/latest_quotes`); current market value per position
- [x] Returns: simple + money-weighted XIRR wired into `portfolio.valuation`
- [x] First portfolio chart — cumulative invested capital over time (Chart.js)
- [x] FX handling (`marketdata.fx`) for multi-currency base-currency aggregation
- [x] Manual "Refresh prices" action + 36 new tests (89% coverage, ruff-clean)

### Stage 2 honesty notes (carry into later stages)
- No quote ⇒ position shows `priced=False` / `—`; we never invent a price.
- Base-currency totals appear only when every currency converts (else `missing_fx`).
- The chart plots **invested capital** (needs no historical prices). True
  mark-to-market history needs a price backfill / daily snapshots — a later stage.
- FX rates are a static `settings.FX_RATES` stop-gap; swap in a live feed later.

## Stage 3 — MVP dashboard ✅ (done)
- [x] Allocation breakdowns by holding / asset class / market / currency
      (`portfolio.allocation`), rendered as Chart.js donuts on the dashboard
- [x] Polished portfolio dashboard: headline stats + allocation + invested chart
- [x] Account overview on the portfolio list: per-portfolio cards + a combined
      single-currency total (`portfolio.overview`)
- [x] Deploy: Render Blueprint (`render.yaml`) for web + worker + beat + Postgres
      + Redis; `Procfile` + `bin/release.sh` for VPS/Docker; Render hostname
      trusted automatically in `prod.py`
- [x] 90% test coverage, ruff-clean

### Stage 3 honesty notes (carry into later stages)
- Allocation uses **market value** only when every position is priced; otherwise
  it falls back to **invested capital** and says so. Unconvertible currencies are
  excluded and listed in `missing_fx` — never mixed without a rate.
- Industry **sector** is intentionally *not* shown: `Asset` has no sector and no
  provider feeds one. Added only when a real data source exists.
- "Performance" is current returns (simple + XIRR) + the invested-capital chart;
  true value-over-time still needs the deferred price backfill / daily snapshots.

## Stage 3.5 — UX polish ✅ (done)
- [x] Branded auth pages actually render — moved allauth templates to project
      `templates/account/` so they stop being shadowed by allauth defaults; the
      signup page got an editorial "benefits + form" layout
- [x] Light/dark theme: token-swap dark mode, header toggle, no-flash inline
      script, OS-preference aware, persisted to `localStorage`
- [x] Internationalisation: en/ru/es/zh-hans via `LocaleMiddleware` + a header
      language switcher; catalogs built with `bin/build_translations.py` (polib,
      no gettext needed); 91 tests incl. template + i18n regression tests

### Still deferred (nice-to-have)
- [ ] Translate asset-class/market data labels + profile/CRUD forms (partial i18n)
- [ ] Industry-sector allocation once a provider feed exists
- [ ] Mark-to-market value-over-time chart (price backfill or `PortfolioSnapshot`)
- [ ] Self-host Chart.js (or SRI + CSP nonce) instead of the CDN tag

## Stage 4 — Monetisation ✅ (done)
- [x] Free/Pro plan service (`billing.subscriptions`): activate/cancel, plan
      limits, `is_pro`
- [x] Free limit enforced — `FREE_MAX_PORTFOLIOS` (default 1) blocks extra
      portfolios with an upsell to pricing; Pro is unlimited
- [x] Payment provider abstraction (`billing.providers`): dev provider simulates
      checkout + HMAC-signed webhooks end-to-end with no keys; YooKassa/Stripe
      slot in once keys exist
- [x] Upgrade → checkout → (dev) confirm → Pro, plus cancel
- [x] Webhook verifies the signature before trusting the body, then activates /
      cancels Pro idempotently
- [x] Pricing + subscription pages wired (i18n + theme); 118 tests, ~92% coverage

### Stage 4 honesty notes
- The **dev** provider takes no real money; the dev-confirm page 404s under a
  real provider so it can never be a free upgrade in production.
- Real provider integration (live API calls) needs keys + a `PaymentProvider`
  implementation — the seam is ready, the calls are not faked.
- Cancel revokes access immediately (MVP); period-end grace is a later refinement.

## Stage 5 — Retention & growth (in progress)
- [x] Yearly **tax report** — FIFO realized gains per lot, grouped by currency,
      with a year selector (`portfolio.tax`); Pro-gated page
- [x] **Export** — transactions + realized-gains report as CSV (UTF-8 BOM) and
      Excel (`portfolio.exports`, openpyxl); Pro-gated downloads
- [x] **Notifications** — in-app list + unread nav badge, per-user email
      preference, and a daily **portfolio digest** (Celery Beat → in-app + email
      for opted-in users); `notifications.services` / `tasks`
- [x] **PDF export** of the tax report (`exports.tax_pdf`, reportlab) alongside
      CSV/Excel; Pro-gated
- [x] **Price alerts** — `marketdata.PriceAlert` + CRUD; evaluated when a quote
      is stored (`marketdata.alerts.check_price_alerts`), fire once → notify
- [x] **Telegram delivery** — best-effort via Bot API (`TELEGRAM_BOT_TOKEN`);
      `notify_user` fans out to email + Telegram per the user's preferences
- [x] **CSV trade import** (`portfolio.imports`) — a keyless stand-in for broker
      auto-import: upload a CSV, valid rows become trades, bad rows are reported
- [ ] Live broker auto-import (e.g. Tinkoff Invest API) — needs broker API keys

### Stage 5 notes
- Realized gains use **FIFO**; figures stay per-currency (never mixed without FX),
  consistent with the rest of the app. Money is Decimal; exports round to 2dp.
- Tax report + exports are **Pro features** (`_ProRequiredMixin` → upsell to
  pricing for Free users). Notifications, alerts and CSV import are available to
  all signed-in users.
- Telegram is **best-effort**: with no `TELEGRAM_BOT_TOKEN` it silently no-ops,
  so in-app + email still work. A live broker API integration is the last
  remaining item and needs credentials.

## Stage 6 — Competitiveness, Tier 1 (in progress)

> Bring the tracker to parity with Intelinvest / Snowball / Sharesight. Each item
> ships as its own branch + PR. Recommended start: dividends (the #1 expected
> feature). See `docs/Freemium-план-развития.md` direction.

- [x] **Dividends & coupons** — manual entry first: a `DividendPayment` model
      (stock/ETF dividend or bond coupon), per-portfolio CRUD, a per-currency
      income summary, yield-on-cost, and a month-by-month calendar/history
      (`portfolio.income`). Free for all signed-in users (core value, not Pro).
- [ ] Auto-pull dividends from MOEX ISS (`/securities/{SECID}/dividends.json`)
      to pre-fill history for RU holdings — the next dividends increment.
- [ ] **Portfolio value over time + benchmark** — `PortfolioSnapshot` + a daily
      job → an honest mark-to-market value chart and index comparison
      (IMOEX / S&P). Closes the deferred mark-to-market chart.
- [ ] **Trade validation** — warn / block selling more than is held (no negative
      positions); surface a clear message instead of silently clamping.

### Stage 6 notes (dividends)
- Income figures stay in the payment's **own currency** and are never summed
  across currencies — same honesty rule as valuation / tax. `net_amount` is
  gross minus tax withheld at source.
- **Yield-on-cost** divides net income by the current open-position cost basis in
  the same currency; it is `None` (em dash) when there's no basis in that
  currency (e.g. the position was fully sold) — never a fabricated yield.
- `paid_on` is the pay date (drives history + the calendar); ex-date and a
  per-share breakdown are deliberately omitted until MOEX auto-pull lands.

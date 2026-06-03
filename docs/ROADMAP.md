# Roadmap

## Stage 1 — Foundation ✅ (done)
- [x] Custom `User` (AbstractUser) + django-allauth (login/signup/logout/reset)
- [x] `Subscription` model + auto-create-on-signup signal
- [x] `Portfolio`, `Asset`, `Transaction` models (Decimal money)
- [x] Manual trade entry (CRUD), ownership-scoped views
- [x] Computed positions + cost basis (`services.compute_positions`)
- [x] App skeletons: marketdata (provider abstraction), analytics (XIRR), billing, notifications
- [x] Split settings, Docker, design system, 85% test coverage, ruff-clean

## Stage 2 — Quotes & analytics (next)
- [ ] Wire Celery + Redis; periodic `refresh_active_quotes`
- [ ] Persist `PriceQuote`; current market value per position
- [ ] Returns: simple + XIRR wired into portfolio summary
- [ ] First portfolio value chart (Chart.js)
- [ ] FX handling for multi-currency base-currency aggregation

## Stage 3 — MVP dashboard
- [ ] Allocation by asset / sector / currency
- [ ] Performance view; polished dashboard
- [ ] Deploy to a VPS / Render

## Stage 4 — Monetisation
- [ ] Free/Pro limits enforced (e.g. 1 portfolio on Free)
- [ ] Payment provider integration + verified webhooks → activate Pro
- [ ] "Pro-only" feature gating

## Stage 5 — Retention & growth
- [ ] Yearly tax report; Excel/PDF export
- [ ] Email/Telegram digests & price alerts
- [ ] Broker auto-import (e.g. Tinkoff Invest API)

"""Portfolio views — class-based, ownership-scoped (Stage 1)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, QuerySet, Sum
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.billing import subscriptions
from apps.marketdata.services import fetch_and_store_quote, resolve_asset_name

from . import exports
from .allocation import build_allocation, chart_payload
from .bonds import bond_summary
from .broker_import import import_broker_xlsx
from .forecast import income_forecast
from .forms import (
    AssetForm,
    BondDetailForm,
    CorporateActionForm,
    DividendForm,
    PortfolioForm,
    TransactionForm,
)
from .imports import import_trades_csv
from .income import (
    dividend_calendar,
    dividend_history,
    dividend_summary,
    dividend_years,
    yield_on_cost,
)
from .models import (
    Asset,
    BondDetail,
    CorporateAction,
    DividendPayment,
    Portfolio,
    RebalanceTarget,
    Transaction,
)
from .overview import build_account_overview
from .rebalance import build_rebalance
from .services import compute_positions, portfolio_summary
from .snapshots import take_snapshot, value_timeseries
from .tax import realized_gains, realized_summary, realized_years
from .valuation import invested_timeseries, portfolio_valuation

# Allocation axes rendered as donut charts on the dashboard. A donut is drawn
# only for an axis with more than one slice — a single-slice pie (e.g. a
# one-currency portfolio) carries no diversification signal.
_MIN_SLICES_FOR_CHART = 2
_ALLOCATION_AXES = (
    (_("By holding"), "holding", "by_holding"),
    (_("By asset class"), "class", "by_class"),
    (_("By market"), "market", "by_market"),
    (_("By currency"), "currency", "by_currency"),
)


# --------------------------------------------------------------------------- #
# Portfolio
# --------------------------------------------------------------------------- #
class PortfolioListView(LoginRequiredMixin, ListView):
    template_name = "portfolio/portfolio_list.html"
    context_object_name = "portfolios"

    def get_queryset(self) -> QuerySet[Portfolio]:
        return self.request.user.portfolios.annotate(
            transaction_count=Count("transactions")
        ).order_by("name")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        # Per-portfolio cards + an optional single-currency combined total.
        ctx["overview"] = build_account_overview(ctx["portfolios"])
        # Plan context drives the "New portfolio" button / upsell.
        ctx["can_create_portfolio"] = subscriptions.can_create_portfolio(
            self.request.user
        )
        ctx["remaining_slots"] = subscriptions.remaining_portfolio_slots(
            self.request.user
        )
        ctx["is_pro"] = subscriptions.is_pro(self.request.user)
        return ctx


class PortfolioCreateView(LoginRequiredMixin, CreateView):
    model = Portfolio
    form_class = PortfolioForm
    template_name = "portfolio/portfolio_form.html"

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        # Enforce the Free-plan portfolio cap before GET (hide form) or POST
        # (block creation); Pro is unlimited. Upsell by redirecting to pricing.
        if request.user.is_authenticated and not subscriptions.can_create_portfolio(
            request.user
        ):
            limit = subscriptions.portfolio_limit(request.user)
            messages.info(
                request,
                _(
                    "Your Free plan is limited to %(limit)s portfolio(s). "
                    "Upgrade to Pro for unlimited portfolios."
                )
                % {"limit": limit},
            )
            return redirect("billing:pricing")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: PortfolioForm):
        form.instance.owner = self.request.user
        messages.success(self.request, _("Portfolio created."))
        return super().form_valid(form)


class _OwnedPortfolioMixin(LoginRequiredMixin):
    """Restrict Portfolio access to the authenticated owner (404 otherwise)."""

    def get_queryset(self) -> QuerySet[Portfolio]:
        return self.request.user.portfolios.all()


class PortfolioDetailView(_OwnedPortfolioMixin, DetailView):
    template_name = "portfolio/portfolio_detail.html"
    context_object_name = "portfolio"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        valuation = portfolio_valuation(self.object)
        # Reuse the already-priced positions so allocation costs no extra query.
        allocation = build_allocation(valuation["positions"], valuation["base_currency"])
        ctx["valuation"] = valuation
        ctx["allocation"] = allocation
        ctx["allocation_charts"] = self._allocation_charts(allocation)
        ctx["chart_data"] = invested_timeseries(self.object)
        # Opportunistically record today's mark-to-market value (free tier has
        # no Celery worker). Stores nothing unless the portfolio is fully priced
        # and convertible — never a fabricated value. Idempotent per day.
        take_snapshot(self.object, valuation=valuation)
        ctx["value_chart"] = value_timeseries(self.object)
        ctx["transactions"] = self.object.transactions.select_related("asset")[:50]
        return ctx

    @staticmethod
    def _allocation_charts(allocation: dict[str, Any]) -> list[dict[str, Any]]:
        """Build per-axis donut data, skipping axes with a single slice."""
        charts: list[dict[str, Any]] = []
        for title, slug, key in _ALLOCATION_AXES:
            slices = allocation[key]
            if len(slices) < _MIN_SLICES_FOR_CHART:
                continue
            charts.append(
                {
                    "title": title,
                    "slices": slices,
                    "dom_id": f"donut-{slug}",
                    "data_id": f"donut-{slug}-data",
                    "payload": chart_payload(slices),
                }
            )
        return charts


class PortfolioRefreshQuotesView(LoginRequiredMixin, View):
    """POST-only: fetch fresh quotes for this portfolio's held assets, inline.

    The free hosting tier has no Celery worker, so quotes are fetched
    synchronously in the request (only a handful of held assets). Each new
    ``PriceQuote`` is persisted and shown on the next page load.
    """

    def post(
        self, request: HttpRequest, *args: Any, pk: int, **kwargs: Any
    ) -> HttpResponse:
        portfolio = get_object_or_404(Portfolio, pk=pk, owner=request.user)
        held = compute_positions(portfolio)
        if not held:
            messages.info(request, "Add a trade first — no positions to price yet.")
            return redirect(portfolio.get_absolute_url())

        # Free tier has no Celery worker — fetch inline (a handful of assets).
        priced = sum(
            1
            for position in held
            if fetch_and_store_quote(position.asset) is not None
        )
        if priced:
            messages.success(
                request, f"Updated prices for {priced} of {len(held)} asset(s)."
            )
        else:
            messages.warning(
                request,
                "Couldn't fetch a price for any holding — check the ticker/market.",
            )
        return redirect(portfolio.get_absolute_url())


class PortfolioUpdateView(_OwnedPortfolioMixin, UpdateView):
    form_class = PortfolioForm
    template_name = "portfolio/portfolio_form.html"


class PortfolioDeleteView(_OwnedPortfolioMixin, DeleteView):
    template_name = "portfolio/portfolio_confirm_delete.html"
    success_url = reverse_lazy("portfolio:list")


# --------------------------------------------------------------------------- #
# Transaction
# --------------------------------------------------------------------------- #
class TransactionCreateView(LoginRequiredMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "portfolio/transaction_form.html"

    def dispatch(self, request, *args: Any, **kwargs: Any):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.portfolio = get_object_or_404(
            Portfolio, pk=kwargs["pk"], owner=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self) -> dict[str, Any]:
        # Give the form the parent portfolio so it can validate a SELL against
        # the units actually held (the instance has no portfolio yet on create).
        kwargs = super().get_form_kwargs()
        kwargs["portfolio"] = self.portfolio
        return kwargs

    def form_valid(self, form: TransactionForm):
        form.instance.portfolio = self.portfolio
        messages.success(self.request, "Transaction added.")
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return self.portfolio.get_absolute_url()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["portfolio"] = self.portfolio
        ctx["assets_exist"] = Asset.objects.exists()
        return ctx


class _OwnedTransactionMixin(LoginRequiredMixin):
    """Restrict Transaction access via the parent portfolio's owner."""

    def get_queryset(self) -> QuerySet[Transaction]:
        return Transaction.objects.filter(
            portfolio__owner=self.request.user
        ).select_related("portfolio", "asset")

    def get_success_url(self) -> str:
        return self.object.portfolio.get_absolute_url()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["portfolio"] = self.object.portfolio
        return ctx


class TransactionUpdateView(_OwnedTransactionMixin, UpdateView):
    form_class = TransactionForm
    template_name = "portfolio/transaction_form.html"


class TransactionDeleteView(_OwnedTransactionMixin, DeleteView):
    template_name = "portfolio/transaction_confirm_delete.html"


# --------------------------------------------------------------------------- #
# Dividends & coupons (Tier 1)
# --------------------------------------------------------------------------- #
class DividendListView(_OwnedPortfolioMixin, DetailView):
    """Per-portfolio dividend/coupon history, calendar and per-currency totals."""

    template_name = "portfolio/dividend_list.html"
    context_object_name = "portfolio"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        years = dividend_years(self.object)
        year = self.kwargs.get("year")
        if year is None and years:
            year = years[0]
        payments = dividend_history(self.object, year=year)
        summary = dividend_summary(payments)
        # Yield-on-cost uses the current open-position cost basis per currency;
        # None when there's no basis in that currency (honest, no fabrication).
        # Attach it onto each currency bucket so the template can render it
        # without a dict-by-variable-key lookup.
        invested = portfolio_summary(self.object)["invested_by_currency"]
        yoc = yield_on_cost(summary, invested)
        for currency, bucket in summary.items():
            bucket["yoc"] = yoc[currency]
        ctx["years"] = years
        ctx["year"] = year
        ctx["payments"] = payments
        ctx["summary"] = summary
        ctx["calendar"] = dividend_calendar(payments)
        return ctx


class DividendCreateView(LoginRequiredMixin, CreateView):
    model = DividendPayment
    form_class = DividendForm
    template_name = "portfolio/dividend_form.html"

    def dispatch(self, request, *args: Any, **kwargs: Any):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.portfolio = get_object_or_404(
            Portfolio, pk=kwargs["pk"], owner=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self) -> dict[str, Any]:
        return {"paid_on": timezone.now().date()}

    def form_valid(self, form: DividendForm):
        form.instance.portfolio = self.portfolio
        messages.success(self.request, _("Dividend recorded."))
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse("portfolio:dividends", kwargs={"pk": self.portfolio.pk})

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["portfolio"] = self.portfolio
        ctx["assets_exist"] = Asset.objects.exists()
        return ctx


class _OwnedDividendMixin(LoginRequiredMixin):
    """Restrict DividendPayment access via the parent portfolio's owner."""

    def get_queryset(self) -> QuerySet[DividendPayment]:
        return DividendPayment.objects.filter(
            portfolio__owner=self.request.user
        ).select_related("portfolio", "asset")

    def get_success_url(self) -> str:
        return reverse("portfolio:dividends", kwargs={"pk": self.object.portfolio.pk})

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["portfolio"] = self.object.portfolio
        return ctx


class DividendUpdateView(_OwnedDividendMixin, UpdateView):
    form_class = DividendForm
    template_name = "portfolio/dividend_form.html"


class DividendDeleteView(_OwnedDividendMixin, DeleteView):
    template_name = "portfolio/dividend_confirm_delete.html"


class IncomeForecastView(_OwnedPortfolioMixin, DetailView):
    """Expected future income (bond coupons) over the next 12 months — Tier 3 (#9)."""

    template_name = "portfolio/income_forecast.html"
    context_object_name = "portfolio"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["forecast"] = income_forecast(self.object)
        return ctx


# --------------------------------------------------------------------------- #
# Bonds — НКД / coupons / maturity (Tier 2 #5)
# --------------------------------------------------------------------------- #
class BondListView(_OwnedPortfolioMixin, DetailView):
    """Held bonds in a portfolio with computed НКД, next coupon and maturity."""

    template_name = "portfolio/bond_list.html"
    context_object_name = "portfolio"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()
        bond_positions = [
            pos for pos in compute_positions(self.object) if pos.asset.asset_type == "BOND"
        ]
        details = {
            bond.asset_id: bond
            for bond in BondDetail.objects.filter(
                asset_id__in=[pos.asset.id for pos in bond_positions]
            )
        }
        rows: list[dict[str, Any]] = []
        for pos in bond_positions:
            detail = details.get(pos.asset.id)
            rows.append(
                {
                    "position": pos,
                    "detail": detail,
                    "summary": bond_summary(detail, today, quantity=pos.quantity)
                    if detail
                    else None,
                }
            )
        ctx["bonds"] = rows
        ctx["today"] = today
        return ctx


class BondDetailUpsertView(LoginRequiredMixin, View):
    """Create or edit the bond reference details for a BOND-type asset."""

    template_name = "portfolio/bond_form.html"

    def _load(self, request: HttpRequest, pk: int, asset_id: int):
        portfolio = get_object_or_404(Portfolio, pk=pk, owner=request.user)
        asset = get_object_or_404(Asset, pk=asset_id, asset_type="BOND")
        detail = BondDetail.objects.filter(asset=asset).first()
        return portfolio, asset, detail

    def get(self, request: HttpRequest, pk: int, asset_id: int, *a: Any, **k: Any) -> HttpResponse:
        portfolio, asset, detail = self._load(request, pk, asset_id)
        form = BondDetailForm(instance=detail)
        return render(
            request, self.template_name,
            {"form": form, "portfolio": portfolio, "asset": asset},
        )

    def post(self, request: HttpRequest, pk: int, asset_id: int, *a: Any, **k: Any) -> HttpResponse:
        portfolio, asset, detail = self._load(request, pk, asset_id)
        form = BondDetailForm(request.POST, instance=detail)
        if form.is_valid():
            bond = form.save(commit=False)
            bond.asset = asset
            bond.save()
            messages.success(request, _("Bond details saved."))
            return redirect("portfolio:bonds", pk=portfolio.pk)
        return render(
            request, self.template_name,
            {"form": form, "portfolio": portfolio, "asset": asset},
        )


# --------------------------------------------------------------------------- #
# Rebalancing — target weights + buy/sell suggestions (Tier 2 #6)
# --------------------------------------------------------------------------- #
class RebalanceView(_OwnedPortfolioMixin, DetailView):
    """Show current vs target allocation; POST saves per-asset target weights."""

    template_name = "portfolio/rebalance.html"
    context_object_name = "portfolio"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["rebalance"] = build_rebalance(self.object)
        return ctx

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        portfolio = self.get_object()  # owner-scoped queryset -> 404 otherwise
        existing = {t.asset_id: t for t in portfolio.rebalance_targets.all()}
        held_ids = [pos.asset.id for pos in compute_positions(portfolio)]
        asset_ids = list(dict.fromkeys(held_ids + list(existing.keys())))

        saved = 0
        invalid = 0
        for asset_id in asset_ids:
            raw = (request.POST.get(f"target_{asset_id}") or "").strip().replace(",", ".")
            if raw == "":
                if asset_id in existing:
                    existing[asset_id].delete()
                continue
            try:
                weight = Decimal(raw)
            except InvalidOperation:
                invalid += 1
                continue
            if weight < 0:
                invalid += 1
                continue
            RebalanceTarget.objects.update_or_create(
                portfolio=portfolio,
                asset_id=asset_id,
                defaults={"target_weight": weight},
            )
            saved += 1

        if saved:
            messages.success(request, _("Target allocation saved."))
        if invalid:
            messages.warning(
                request, _("Some targets were invalid and skipped (use a number ≥ 0).")
            )
        total = portfolio.rebalance_targets.aggregate(s=Sum("target_weight"))["s"]
        if total and total > Decimal("100"):
            messages.info(
                request,
                _("Targets add up to %(sum)s%% — over 100%%.") % {"sum": total},
            )
        return redirect("portfolio:rebalance", pk=portfolio.pk)


# --------------------------------------------------------------------------- #
# Corporate actions — stock splits (Tier 2 #7)
# --------------------------------------------------------------------------- #
class CorporateActionsView(_OwnedPortfolioMixin, DetailView):
    """List splits affecting the portfolio's assets; POST adds a split."""

    template_name = "portfolio/corporate_action_list.html"
    context_object_name = "portfolio"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", CorporateActionForm(portfolio=self.object))
        ctx["actions"] = (
            CorporateAction.objects.filter(asset__transactions__portfolio=self.object)
            .select_related("asset")
            .distinct()
        )
        return ctx

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()  # owner-scoped -> 404 otherwise
        form = CorporateActionForm(request.POST, portfolio=self.object)
        if form.is_valid():
            form.save()
            messages.success(request, _("Corporate action saved."))
            return redirect("portfolio:corporate_actions", pk=self.object.pk)
        return self.render_to_response(self.get_context_data(form=form))


class CorporateActionDeleteView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, pk: int, action_id: int, *a: Any, **k: Any) -> HttpResponse:
        portfolio = get_object_or_404(Portfolio, pk=pk, owner=request.user)
        action = get_object_or_404(CorporateAction, pk=action_id)
        # Only allow removing a split for an asset actually traded in this portfolio.
        if not action.asset.transactions.filter(portfolio=portfolio).exists():
            raise Http404
        action.delete()
        messages.success(request, _("Corporate action removed."))
        return redirect("portfolio:corporate_actions", pk=portfolio.pk)


# --------------------------------------------------------------------------- #
# Asset catalogue (shared reference table)
# --------------------------------------------------------------------------- #
class AssetListView(LoginRequiredMixin, ListView):
    model = Asset
    template_name = "portfolio/asset_list.html"
    context_object_name = "assets"
    paginate_by = 50


class AssetCreateView(LoginRequiredMixin, CreateView):
    model = Asset
    form_class = AssetForm
    template_name = "portfolio/asset_form.html"
    success_url = reverse_lazy("portfolio:asset_list")

    def form_valid(self, form: AssetForm):
        response = super().form_valid(form)
        # Auto-fill the company / security name from the market provider when the
        # user left it blank, so we always know which instrument this is.
        if not self.object.name:
            name = resolve_asset_name(self.object.market, self.object.ticker)
            if name:
                self.object.name = name
                self.object.save(update_fields=["name"])
        messages.success(self.request, _("Asset added to the catalogue."))
        return response


class AssetDeleteView(LoginRequiredMixin, DeleteView):
    model = Asset
    template_name = "portfolio/asset_confirm_delete.html"
    success_url = reverse_lazy("portfolio:asset_list")

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        # Asset is a shared catalogue row; refuse deletion while trades reference
        # it (FK is PROTECT) so we never orphan a portfolio's history.
        asset = self.get_object()
        if asset.transactions.exists():
            messages.error(
                request,
                _("Can't delete %(ticker)s — it still has trades. Remove them first.")
                % {"ticker": asset.ticker},
            )
            return redirect("portfolio:asset_list")
        messages.success(request, _("Asset deleted."))
        return super().post(request, *args, **kwargs)


# --------------------------------------------------------------------------- #
# CSV trade import (Stage 5 — broker-import stand-in)
# --------------------------------------------------------------------------- #
class ImportTradesView(LoginRequiredMixin, View):
    template_name = "portfolio/import_trades.html"

    def _portfolio(self, request: HttpRequest, pk: int) -> Portfolio:
        return get_object_or_404(Portfolio, pk=pk, owner=request.user)

    def get(self, request: HttpRequest, pk: int, *a: Any, **k: Any) -> HttpResponse:
        return render(request, self.template_name, {"portfolio": self._portfolio(request, pk)})

    def post(self, request: HttpRequest, pk: int, *a: Any, **k: Any) -> HttpResponse:
        portfolio = self._portfolio(request, pk)
        upload = request.FILES.get("file")
        if upload is None:
            messages.error(request, _("Please choose a CSV or .xlsx file."))
            return redirect("portfolio:import_trades", pk=pk)

        # Dispatch by file type: an .xlsx is treated as a broker report (tolerant
        # parser, auto-creates unknown tickers); anything else as our strict CSV.
        if (upload.name or "").lower().endswith(".xlsx"):
            result = import_broker_xlsx(portfolio, upload.read())
        else:
            result = import_trades_csv(portfolio, upload.read())

        if result["created"]:
            messages.success(
                request,
                _("Imported %(n)s trade(s).") % {"n": result["created"]},
            )
        created_assets = result.get("created_assets") or []
        if created_assets:
            messages.info(
                request,
                _("Added %(n)s new instrument(s) to the catalogue: %(tickers)s")
                % {"n": len(created_assets), "tickers": ", ".join(created_assets[:20])},
            )
        for error in result["errors"][:10]:
            messages.warning(request, error)
        if not result["created"] and not result["errors"]:
            messages.info(request, _("No rows found in the file."))
        return redirect(portfolio.get_absolute_url())


# --------------------------------------------------------------------------- #
# Pro: tax report + exports (Stage 5)
# --------------------------------------------------------------------------- #
class _ProRequiredMixin(LoginRequiredMixin):
    """Gate a view behind active Pro; upsell to pricing for Free users."""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        if request.user.is_authenticated and not subscriptions.is_pro(request.user):
            messages.info(
                request,
                _("That's a Pro feature. Upgrade to unlock tax reports and exports."),
            )
            return redirect("billing:pricing")
        return super().dispatch(request, *args, **kwargs)


class TaxReportView(_ProRequiredMixin, _OwnedPortfolioMixin, DetailView):
    """Per-portfolio yearly realized-gains report (Pro)."""

    template_name = "portfolio/tax_report.html"
    context_object_name = "portfolio"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        years = realized_years(self.object)
        year = self.kwargs.get("year")
        if year is None and years:
            year = years[0]
        lots = realized_gains(self.object, year=year)
        ctx["years"] = years
        ctx["year"] = year
        ctx["lots"] = lots
        ctx["summary"] = realized_summary(lots)
        return ctx


def _owned_portfolio(request: HttpRequest, pk: int) -> Portfolio:
    return get_object_or_404(Portfolio, pk=pk, owner=request.user)


def _download(content: bytes, content_type: str, filename: str) -> HttpResponse:
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class ExportTransactionsCsvView(_ProRequiredMixin, View):
    def get(self, request: HttpRequest, pk: int, *a: Any, **k: Any) -> HttpResponse:
        portfolio = _owned_portfolio(request, pk)
        return _download(
            exports.transactions_csv(portfolio),
            "text/csv; charset=utf-8",
            f"{portfolio.name}-transactions.csv",
        )


class ExportTaxCsvView(_ProRequiredMixin, View):
    def get(self, request: HttpRequest, pk: int, *a: Any, **k: Any) -> HttpResponse:
        portfolio = _owned_portfolio(request, pk)
        year = _parse_year(request)
        return _download(
            exports.tax_csv(portfolio, year),
            "text/csv; charset=utf-8",
            f"{portfolio.name}-tax-{year or 'all'}.csv",
        )


class ExportTaxXlsxView(_ProRequiredMixin, View):
    def get(self, request: HttpRequest, pk: int, *a: Any, **k: Any) -> HttpResponse:
        portfolio = _owned_portfolio(request, pk)
        year = _parse_year(request)
        return _download(
            exports.tax_xlsx(portfolio, year),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"{portfolio.name}-tax-{year or 'all'}.xlsx",
        )


class ExportTaxPdfView(_ProRequiredMixin, View):
    def get(self, request: HttpRequest, pk: int, *a: Any, **k: Any) -> HttpResponse:
        portfolio = _owned_portfolio(request, pk)
        year = _parse_year(request)
        return _download(
            exports.tax_pdf(portfolio, year),
            "application/pdf",
            f"{portfolio.name}-tax-{year or 'all'}.pdf",
        )


def _parse_year(request: HttpRequest) -> int | None:
    raw = request.GET.get("year")
    if raw and raw.isdigit():
        return int(raw)
    return None

"""Portfolio views — class-based, ownership-scoped (Stage 1)."""
from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
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
from apps.marketdata.tasks import refresh_quote

from .allocation import build_allocation, chart_payload
from .forms import AssetForm, PortfolioForm, TransactionForm
from .models import Asset, Portfolio, Transaction
from .overview import build_account_overview
from .services import compute_positions
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
    """POST-only: enqueue a fresh-quote refresh for this portfolio's held assets.

    Under ``CELERY_TASK_ALWAYS_EAGER`` (dev) the fetch runs inline so prices
    appear immediately; in production it queues work for the Celery worker.
    """

    def post(
        self, request: HttpRequest, *args: Any, pk: int, **kwargs: Any
    ) -> HttpResponse:
        portfolio = get_object_or_404(Portfolio, pk=pk, owner=request.user)
        held = compute_positions(portfolio)
        for position in held:
            refresh_quote.delay(position.asset.id)

        if held:
            messages.success(
                request, f"Refreshing quotes for {len(held)} asset(s)…"
            )
        else:
            messages.info(request, "Add a trade first — no positions to price yet.")
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
        messages.success(self.request, "Asset added to the catalogue.")
        return super().form_valid(form)

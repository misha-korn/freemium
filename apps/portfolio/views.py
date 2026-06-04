"""Portfolio views — class-based, ownership-scoped (Stage 1)."""
from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.marketdata.tasks import refresh_quote

from .forms import AssetForm, PortfolioForm, TransactionForm
from .models import Asset, Portfolio, Transaction
from .services import compute_positions
from .valuation import invested_timeseries, portfolio_valuation


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


class PortfolioCreateView(LoginRequiredMixin, CreateView):
    model = Portfolio
    form_class = PortfolioForm
    template_name = "portfolio/portfolio_form.html"

    def form_valid(self, form: PortfolioForm):
        form.instance.owner = self.request.user
        messages.success(self.request, "Portfolio created.")
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
        ctx["valuation"] = portfolio_valuation(self.object)
        ctx["chart_data"] = invested_timeseries(self.object)
        ctx["transactions"] = self.object.transactions.select_related("asset")[:50]
        return ctx


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

from django.urls import path

from . import views

app_name = "portfolio"

urlpatterns = [
    path("", views.PortfolioListView.as_view(), name="list"),
    path("new/", views.PortfolioCreateView.as_view(), name="create"),
    path("assets/", views.AssetListView.as_view(), name="asset_list"),
    path("assets/new/", views.AssetCreateView.as_view(), name="asset_create"),
    path("assets/<int:pk>/delete/", views.AssetDeleteView.as_view(), name="asset_delete"),
    path("<int:pk>/", views.PortfolioDetailView.as_view(), name="detail"),
    path(
        "<int:pk>/refresh-quotes/",
        views.PortfolioRefreshQuotesView.as_view(),
        name="refresh_quotes",
    ),
    path("<int:pk>/edit/", views.PortfolioUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.PortfolioDeleteView.as_view(), name="delete"),
    # CSV trade import (Stage 5)
    path("<int:pk>/import/", views.ImportTradesView.as_view(), name="import_trades"),
    # Pro: tax report + exports (Stage 5)
    path("<int:pk>/tax/", views.TaxReportView.as_view(), name="tax_report"),
    path("<int:pk>/tax/<int:year>/", views.TaxReportView.as_view(), name="tax_report_year"),
    path(
        "<int:pk>/export/transactions.csv",
        views.ExportTransactionsCsvView.as_view(),
        name="export_transactions_csv",
    ),
    path("<int:pk>/export/tax.csv", views.ExportTaxCsvView.as_view(), name="export_tax_csv"),
    path("<int:pk>/export/tax.xlsx", views.ExportTaxXlsxView.as_view(), name="export_tax_xlsx"),
    path("<int:pk>/export/tax.pdf", views.ExportTaxPdfView.as_view(), name="export_tax_pdf"),
    path(
        "<int:pk>/transactions/new/",
        views.TransactionCreateView.as_view(),
        name="transaction_create",
    ),
    path(
        "transactions/<int:pk>/edit/",
        views.TransactionUpdateView.as_view(),
        name="transaction_update",
    ),
    path(
        "transactions/<int:pk>/delete/",
        views.TransactionDeleteView.as_view(),
        name="transaction_delete",
    ),
    # Dividends & coupons (Tier 1)
    path("<int:pk>/dividends/", views.DividendListView.as_view(), name="dividends"),
    path(
        "<int:pk>/dividends/new/",
        views.DividendCreateView.as_view(),
        name="dividend_create",
    ),
    path(
        "<int:pk>/dividends/<int:year>/",
        views.DividendListView.as_view(),
        name="dividends_year",
    ),
    path(
        "dividends/<int:pk>/edit/",
        views.DividendUpdateView.as_view(),
        name="dividend_update",
    ),
    path(
        "dividends/<int:pk>/delete/",
        views.DividendDeleteView.as_view(),
        name="dividend_delete",
    ),
    # Income forecast — expected bond coupons (Tier 3 #9)
    path("<int:pk>/income/", views.IncomeForecastView.as_view(), name="income_forecast"),
    # Bonds — НКД / coupons / maturity (Tier 2 #5)
    path("<int:pk>/bonds/", views.BondListView.as_view(), name="bonds"),
    path(
        "<int:pk>/bonds/<int:asset_id>/edit/",
        views.BondDetailUpsertView.as_view(),
        name="bond_edit",
    ),
    # Rebalancing — target weights + suggestions (Tier 2 #6)
    path("<int:pk>/rebalance/", views.RebalanceView.as_view(), name="rebalance"),
    # Corporate actions — stock splits (Tier 2 #7)
    path(
        "<int:pk>/corporate-actions/",
        views.CorporateActionsView.as_view(),
        name="corporate_actions",
    ),
    path(
        "<int:pk>/corporate-actions/<int:action_id>/delete/",
        views.CorporateActionDeleteView.as_view(),
        name="corporate_action_delete",
    ),
]

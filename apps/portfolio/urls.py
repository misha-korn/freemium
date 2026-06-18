from django.urls import path

from . import views

app_name = "portfolio"

urlpatterns = [
    path("", views.PortfolioListView.as_view(), name="list"),
    path("new/", views.PortfolioCreateView.as_view(), name="create"),
    path("assets/", views.AssetListView.as_view(), name="asset_list"),
    path("assets/new/", views.AssetCreateView.as_view(), name="asset_create"),
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
]

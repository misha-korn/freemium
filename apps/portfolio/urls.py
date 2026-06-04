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

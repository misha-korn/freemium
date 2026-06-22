from django.urls import path

from . import views

app_name = "marketdata"

urlpatterns = [
    path("", views.AlertListView.as_view(), name="alert_list"),
    path("new/", views.AlertCreateView.as_view(), name="alert_create"),
    path("<int:pk>/delete/", views.AlertDeleteView.as_view(), name="alert_delete"),
    path("search/", views.SymbolSearchView.as_view(), name="symbol_search"),
]

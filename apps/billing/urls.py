from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("", views.PricingView.as_view(), name="pricing"),
    path("upgrade/", views.UpgradeView.as_view(), name="upgrade"),
    path(
        "dev/confirm/<int:payment_id>/",
        views.DevConfirmView.as_view(),
        name="dev_confirm",
    ),
    path("cancel/", views.CancelView.as_view(), name="cancel"),
    path("webhook/<str:provider>/", views.webhook, name="webhook"),
]

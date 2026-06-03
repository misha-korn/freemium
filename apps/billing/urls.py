from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("", views.PricingView.as_view(), name="pricing"),
    path("webhook/<str:provider>/", views.webhook, name="webhook"),
]

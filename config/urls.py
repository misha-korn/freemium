"""Root URL configuration."""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    # django-allauth: login, signup, logout, password reset, email mgmt, ...
    path("accounts/", include("allauth.account.urls")),
    # App routes
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("u/", include("apps.accounts.urls")),
    path("portfolio/", include("apps.portfolio.urls")),
    path("billing/", include("apps.billing.urls")),
]

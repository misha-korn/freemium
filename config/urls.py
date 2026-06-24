"""Root URL configuration."""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from apps.portfolio.views import PublicPortfolioView

from . import views as pwa_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # PWA (Tier 3): served from root so the service worker controls the whole app.
    path("manifest.webmanifest", pwa_views.manifest, name="manifest"),
    path("sw.js", pwa_views.service_worker, name="service_worker"),
    path("offline/", pwa_views.offline, name="offline"),
    # Public read-only portfolio share link (Tier 3 #10) — short, token-gated.
    path("p/<str:token>/", PublicPortfolioView.as_view(), name="public_portfolio"),
    # i18n set_language view (POST) powers the header language switcher.
    path("i18n/", include("django.conf.urls.i18n")),
    # django-allauth: login, signup, logout, password reset, email mgmt, ...
    path("accounts/", include("allauth.account.urls")),
    # App routes
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path(
        "privacy/",
        TemplateView.as_view(template_name="legal/privacy.html"),
        name="privacy",
    ),
    path("u/", include("apps.accounts.urls")),
    path("portfolio/", include("apps.portfolio.urls")),
    path("billing/", include("apps.billing.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("alerts/", include("apps.marketdata.urls")),
]

"""Project-level views for the PWA (Tier 3 #8).

The web app manifest, service worker and offline fallback are served from the
site root so the service worker's scope covers the whole app (a worker served
from /static/... would only control that path).
"""
from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def manifest(request: HttpRequest) -> HttpResponse:
    """Web app manifest (makes the site installable)."""
    return render(
        request, "pwa/manifest.webmanifest", content_type="application/manifest+json"
    )


def service_worker(request: HttpRequest) -> HttpResponse:
    """Service worker, served at the root so its scope is the whole app."""
    response = render(request, "pwa/sw.js", content_type="application/javascript")
    # Allow root scope explicitly and always revalidate the worker itself.
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def offline(request: HttpRequest) -> HttpResponse:
    """Standalone offline fallback page (precached by the service worker)."""
    return render(request, "pwa/offline.html")

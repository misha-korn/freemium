"""PWA: manifest, service worker, offline page and head wiring (Tier 3 #8)."""
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_manifest_served_with_correct_type_and_fields(client):
    resp = client.get(reverse("manifest"))
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/manifest+json")
    body = resp.content.decode()
    assert '"start_url": "/"' in body
    assert '"display": "standalone"' in body
    assert "icon-192.png" in body
    assert '"purpose": "maskable"' in body


@pytest.mark.django_db
def test_service_worker_served_at_root_scope(client):
    resp = client.get(reverse("service_worker"))
    assert resp.status_code == 200
    assert "javascript" in resp["Content-Type"]
    # Root scope + always-revalidate so worker updates propagate.
    assert resp["Service-Worker-Allowed"] == "/"
    body = resp.content.decode()
    assert 'addEventListener("fetch"' in body
    assert "/offline/" in body


@pytest.mark.django_db
def test_offline_page_renders(client):
    resp = client.get(reverse("offline"))
    assert resp.status_code == 200
    assert b"You&#x27;re offline" in resp.content or b"You're offline" in resp.content


@pytest.mark.django_db
def test_base_head_wires_pwa(client):
    html = client.get(reverse("home")).content.decode()
    assert 'rel="manifest"' in html
    assert 'name="theme-color"' in html
    assert "js/pwa.js" in html
    assert 'rel="apple-touch-icon"' in html


@pytest.mark.django_db
def test_offline_page_translates_to_russian(client):
    client.post(reverse("set_language"), {"language": "ru", "next": "/"})
    html = client.get(reverse("offline")).content.decode()
    assert "Вы офлайн" in html

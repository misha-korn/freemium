"""Notification view tests: list, mark-read, preferences, nav badge (Stage 5)."""
import pytest
from django.urls import reverse

from apps.notifications import services
from apps.notifications.models import NotificationPreference


@pytest.mark.django_db
def test_list_requires_login(client):
    resp = client.get(reverse("notifications:list"))
    assert resp.status_code == 302
    assert "/accounts/login" in resp.url


@pytest.mark.django_db
def test_list_shows_notifications(auth_client, user):
    services.notify(user, "X", "Hello there")
    resp = auth_client.get(reverse("notifications:list"))
    assert resp.status_code == 200
    assert b"Hello there" in resp.content


@pytest.mark.django_db
def test_list_scoped_to_user(auth_client, other_user):
    services.notify(other_user, "X", "Secret of someone else")
    resp = auth_client.get(reverse("notifications:list"))
    assert b"Secret of someone else" not in resp.content


@pytest.mark.django_db
def test_mark_all_read(auth_client, user):
    services.notify(user, "X", "a")
    services.notify(user, "X", "b")
    resp = auth_client.post(reverse("notifications:mark_all_read"))
    assert resp.status_code == 302
    assert services.unread_count(user) == 0


@pytest.mark.django_db
def test_preferences_toggle_off(auth_client, user):
    resp = auth_client.post(reverse("notifications:preferences"), {})  # checkbox absent
    assert resp.status_code == 302
    pref = NotificationPreference.objects.get(user=user)
    assert pref.email_enabled is False


@pytest.mark.django_db
def test_unread_badge_in_context(auth_client, user):
    services.notify(user, "X", "a")
    resp = auth_client.get(reverse("portfolio:list"))
    assert resp.context["unread_notifications"] == 1

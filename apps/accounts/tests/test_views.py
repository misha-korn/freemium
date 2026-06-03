import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_profile_requires_login(client):
    resp = client.get(reverse("accounts:profile"))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_profile_renders_for_authed_user(auth_client):
    resp = auth_client.get(reverse("accounts:profile"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_profile_edit_rejects_duplicate_email(auth_client, user, other_user):
    resp = auth_client.post(
        reverse("accounts:profile_edit"),
        {"first_name": "A", "last_name": "B", "email": other_user.email},
    )
    assert resp.status_code == 200  # re-rendered with validation error
    user.refresh_from_db()
    assert user.email != other_user.email


@pytest.mark.django_db
def test_public_pages_render(client):
    """Home + allauth login/signup overrides render without template errors."""
    assert client.get(reverse("home")).status_code == 200
    assert client.get(reverse("account_login")).status_code == 200
    assert client.get(reverse("account_signup")).status_code == 200

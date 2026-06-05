"""Regression tests for Stage 3.5 UX: branded auth templates + i18n.

The allauth templates once lost to allauth's own defaults because
``allauth.account`` precedes ``apps.accounts`` in INSTALLED_APPS; moving them to
project-level ``templates/account/`` fixed it. These tests lock that in, plus the
language switcher actually translating content.
"""
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_signup_renders_branded_template(client):
    resp = client.get(reverse("account_signup"))
    assert resp.status_code == 200
    html = resp.content.decode()
    # Markers unique to our template + base, not allauth's default page.
    assert "Create your account" in html
    assert "brand__name" in html
    assert "auth-benefits" in html


@pytest.mark.django_db
def test_login_renders_branded_template(client):
    resp = client.get(reverse("account_login"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Forgot password?" in html
    assert "brand__name" in html


@pytest.mark.django_db
def test_base_exposes_theme_toggle_and_language_switcher(client):
    html = client.get(reverse("home")).content.decode()
    assert 'id="theme-toggle"' in html
    assert "data-lang-switcher" in html
    # No-flash theme script must be inline in <head>.
    assert 'localStorage.getItem("theme")' in html


@pytest.mark.django_db
def test_language_switch_translates_home(client):
    # Default language (English) content.
    html_en = client.get(reverse("home")).content.decode()
    assert "Personal investment tracker" in html_en

    # Switch to Russian via the i18n set_language view, then re-fetch.
    resp = client.post(
        reverse("set_language"), {"language": "ru", "next": "/"}
    )
    assert resp.status_code == 302
    html_ru = client.get(reverse("home")).content.decode()
    assert "Личный трекер инвестиций" in html_ru
    assert 'lang="ru"' in html_ru


@pytest.mark.django_db
def test_language_switch_to_chinese(client):
    client.post(reverse("set_language"), {"language": "zh-hans", "next": "/"})
    html = client.get(reverse("home")).content.decode()
    assert "个人投资追踪器" in html
    assert 'lang="zh-hans"' in html

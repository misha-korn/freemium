"""Tests for notification service extensions + digest builder (Stage 5)."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.core import mail

from apps.notifications import services
from apps.notifications.models import Notification, NotificationPreference
from apps.portfolio.models import Asset, Portfolio, Transaction


@pytest.mark.django_db
def test_get_preference_creates_once(user):
    pref = services.get_preference(user)
    assert isinstance(pref, NotificationPreference)
    assert services.get_preference(user).pk == pref.pk  # idempotent


@pytest.mark.django_db
def test_notify_user_emails_when_enabled(user, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox = []
    services.get_preference(user)  # email_enabled defaults True
    note = services.notify_user(user, "DIGEST", "Hi", "Body")
    assert isinstance(note, Notification)
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Hi"


@pytest.mark.django_db
def test_notify_user_skips_email_when_disabled(user, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox = []
    pref = services.get_preference(user)
    pref.email_enabled = False
    pref.save()
    services.notify_user(user, "DIGEST", "Hi", "Body")
    assert len(mail.outbox) == 0  # in-app only


@pytest.mark.django_db
def test_unread_count_and_mark_all_read(user):
    services.notify(user, "X", "a")
    services.notify(user, "X", "b")
    assert services.unread_count(user) == 2
    marked = services.mark_all_read(user)
    assert marked == 2
    assert services.unread_count(user) == 0


@pytest.mark.django_db
def test_build_portfolio_digest_summarises_holdings(user):
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    pf = Portfolio.objects.create(owner=user, name="Growth", base_currency="USD")
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("10"),
        price=Decimal("100"), fee=Decimal("0"), executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    from apps.marketdata.models import PriceQuote
    PriceQuote.objects.create(
        asset=asset, price=Decimal("150"), currency="USD",
        as_of=datetime.now(UTC), source="TEST",
    )

    digest = services.build_portfolio_digest(user)
    assert digest is not None
    assert "Growth" in digest
    assert "USD" in digest


@pytest.mark.django_db
def test_build_portfolio_digest_none_without_portfolios(user):
    assert services.build_portfolio_digest(user) is None


@pytest.mark.django_db
def test_send_telegram_posts_when_configured(user, settings, monkeypatch):
    settings.TELEGRAM_BOT_TOKEN = "token123"
    pref = services.get_preference(user)
    pref.telegram_enabled = True
    pref.telegram_chat_id = "555"
    pref.save()

    calls = {}

    class _Resp:
        def raise_for_status(self) -> None:
            return None

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["json"] = kwargs.get("json")
        return _Resp()

    monkeypatch.setattr("apps.notifications.services.requests.post", fake_post)
    assert services.send_telegram(pref, "Hello") is True
    assert "token123" in calls["url"]
    assert calls["json"]["chat_id"] == "555"
    assert calls["json"]["text"] == "Hello"


@pytest.mark.django_db
def test_send_telegram_skips_without_token(user, settings):
    settings.TELEGRAM_BOT_TOKEN = ""
    pref = services.get_preference(user)
    pref.telegram_enabled = True
    pref.telegram_chat_id = "555"
    pref.save()
    assert services.send_telegram(pref, "Hi") is False


@pytest.mark.django_db
def test_send_daily_digest_notifies_users_with_holdings(user, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox = []
    asset = Asset.objects.create(
        ticker="AAPL", asset_type="STOCK", market="US", currency="USD"
    )
    pf = Portfolio.objects.create(owner=user, name="Growth", base_currency="USD")
    Transaction.objects.create(
        portfolio=pf, asset=asset, kind="BUY", quantity=Decimal("10"),
        price=Decimal("100"), fee=Decimal("0"), executed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    from apps.notifications.tasks import send_daily_digest
    sent = send_daily_digest()

    assert sent == 1
    assert Notification.objects.filter(user=user, kind="DIGEST").count() == 1
    assert len(mail.outbox) == 1  # email pref defaults on

import pytest
from django.contrib.auth import get_user_model

from apps.notifications.models import Notification
from apps.notifications.services import notify, send_email_notification


@pytest.mark.django_db
def test_notify_creates_notification(user):
    notification = notify(user, kind="PRICE_ALERT", title="Hello", body="Body text")

    assert isinstance(notification, Notification)
    assert notification.title == "Hello"
    assert notification.kind == "PRICE_ALERT"
    assert Notification.objects.filter(user=user, kind="PRICE_ALERT").count() == 1


@pytest.mark.django_db
def test_send_email_notification_sends_when_email_present(user):
    notification = notify(user, kind="X", title="Subject", body="Body")
    assert send_email_notification(notification) is True


@pytest.mark.django_db
def test_send_email_notification_false_without_email():
    no_email_user = get_user_model().objects.create_user(
        username="noemail", email="", password="pw-12345!"
    )
    notification = notify(no_email_user, kind="X", title="Subject", body="Body")
    assert send_email_notification(notification) is False

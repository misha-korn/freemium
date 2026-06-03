"""Notification models — in-app records + per-user delivery preferences.

Email/Telegram digests are delivered via Celery from Stage 5.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


class Notification(models.Model):
    """An in-app notification for a user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.kind}: {self.title}"


class NotificationPreference(models.Model):
    """Per-user channel preferences."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_prefs",
    )
    email_enabled = models.BooleanField(default=True)
    telegram_enabled = models.BooleanField(default=False)
    telegram_chat_id = models.CharField(max_length=64, blank=True)

    def __str__(self) -> str:
        return f"Notification prefs for {self.user}"

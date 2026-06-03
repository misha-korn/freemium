from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts & subscriptions"

    def ready(self) -> None:
        """Wire up signal handlers."""
        from . import signals  # noqa: F401

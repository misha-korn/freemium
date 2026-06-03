from django.contrib import admin

from .models import Payment, WebhookEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "amount",
        "currency",
        "provider",
        "purpose",
        "status",
        "created_at",
    )
    list_filter = ("provider", "purpose", "status", "currency")
    search_fields = ("user__username", "user__email", "provider_payment_id")
    autocomplete_fields = ("user",)
    date_hierarchy = "created_at"


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_id", "processed", "received_at")
    list_filter = ("provider", "processed")
    search_fields = ("event_id",)
    date_hierarchy = "received_at"

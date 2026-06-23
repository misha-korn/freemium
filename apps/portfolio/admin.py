from django.contrib import admin

from .models import Asset, DividendPayment, Portfolio, Transaction


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "base_currency", "created_at")
    list_filter = ("base_currency",)
    search_fields = ("name", "owner__username", "owner__email")
    autocomplete_fields = ("owner",)
    date_hierarchy = "created_at"


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("ticker", "name", "asset_type", "market", "currency")
    list_filter = ("asset_type", "market", "currency")
    search_fields = ("ticker", "name", "isin")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "executed_at",
        "portfolio",
        "asset",
        "kind",
        "quantity",
        "price",
        "fee",
    )
    list_filter = ("kind", "asset__market", "asset__asset_type")
    search_fields = ("portfolio__name", "asset__ticker", "note")
    autocomplete_fields = ("portfolio", "asset")
    date_hierarchy = "executed_at"


@admin.register(DividendPayment)
class DividendPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "paid_on",
        "portfolio",
        "asset",
        "kind",
        "amount",
        "tax_withheld",
        "currency",
    )
    list_filter = ("kind", "currency", "asset__market")
    search_fields = ("portfolio__name", "asset__ticker", "note")
    autocomplete_fields = ("portfolio", "asset")
    date_hierarchy = "paid_on"

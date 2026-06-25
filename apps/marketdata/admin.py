from django.contrib import admin

from .models import AssetDividend, PriceQuote


@admin.register(PriceQuote)
class PriceQuoteAdmin(admin.ModelAdmin):
    list_display = ("asset", "price", "currency", "as_of", "source")
    list_filter = ("source", "currency")
    search_fields = ("asset__ticker",)
    autocomplete_fields = ("asset",)
    date_hierarchy = "as_of"


@admin.register(AssetDividend)
class AssetDividendAdmin(admin.ModelAdmin):
    list_display = ("asset", "ex_date", "amount", "currency", "source")
    list_filter = ("source", "currency")
    search_fields = ("asset__ticker",)
    autocomplete_fields = ("asset",)
    date_hierarchy = "ex_date"

from django.contrib import admin

from .models import PeriodicRetain


@admin.register(PeriodicRetain)
class PeriodicRetainAdmin(admin.ModelAdmin):
    list_display = (
        "payment_card_account",
        "status",
        "message_key",
        "succeeded",
        "retry_count",
        "created",
        "updated",
    )
    list_filter = ("status", "succeeded", "message_key")
    readonly_fields = (
        "payment_card_account",
        "status",
        "retry_count",
        "results",
        "created",
        "updated",
    )
    search_fields = ("id", "status", "data", "results")
    list_per_page = 500

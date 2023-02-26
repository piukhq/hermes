from django.contrib import admin
from rangefilter.filters import DateTimeRangeFilter

from .models import PeriodicRetain, RetryStatus


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
    list_filter = (
        "status",
        "succeeded",
        "message_key",
        ("updated", DateTimeRangeFilter),
        ("created", DateTimeRangeFilter),
    )
    readonly_fields = (
        "payment_card_account",
        "message_key",
        "succeeded",
        "retry_count",
        "results",
        "created",
        "updated",
    )
    search_fields = ("status", "message_key", "results")
    list_per_page = 500
    actions = ["retry", "stop"]

    def retry(self, request, queryset):
        for retain in queryset:
            retain.status = RetryStatus.RETRYING
            retain.save()

    def stop(self, request, queryset):
        for retain in queryset:
            retain.status = RetryStatus.STOPPED
            retain.save()

import arrow
from django.contrib import admin
from rangefilter.filters import DateTimeRangeFilter

from .models import PeriodicRetain, RetryStatus
from .tasks import retain_pending_payments


@admin.register(PeriodicRetain)
class PeriodicRetainAdmin(admin.ModelAdmin):
    list_display = (
        "payment_card_account",
        "status",
        "message_key",
        "succeeded",
        "retry_count",
        "account_created",
        "hours_old",
        "created",
        "updated",
    )
    list_filter = (
        "status",
        "succeeded",
        "message_key",
        ("updated", DateTimeRangeFilter),
        ("created", DateTimeRangeFilter),
        ("payment_card_account__created", DateTimeRangeFilter),
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
        queryset.update(status=RetryStatus.RETRYING, created=arrow.utcnow().format())
        retain_pending_payments()

    def stop(self, request, queryset):
        queryset.update(status=RetryStatus.STOPPED)

    def account_created(self, obj):
        return obj.payment_card_account.created

    def hours_old(self, obj):
        return round((arrow.utcnow() - obj.payment_card_account.created).total_seconds() / 3600, 2)

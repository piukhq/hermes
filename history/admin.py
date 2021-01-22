from django.contrib import admin
from rangefilter.filter import DateTimeRangeFilter

from common.admin import InputFilter
from history.models import (
    HistoricalPaymentCardAccount,
    HistoricalSchemeAccount,
    HistoricalPaymentCardAccountEntry,
    HistoricalSchemeAccountEntry,
)


class PaymentCardAccountFilter(InputFilter):
    parameter_name = "payment_card_account_id"
    title = "Payment Card Account ID:"

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        if "Entry" in queryset.model.__name__:
            query = {"payment_card_account_id": term}
        else:
            query = {"instance_id": term}

        return queryset.filter(**query)


class SchemeAccountFilter(InputFilter):
    parameter_name = "scheme_account_id"
    title = "Scheme Account ID:"

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        if "Entry" in queryset.model.__name__:
            query = {"scheme_account_id": term}
        else:
            query = {"instance_id": term}

        return queryset.filter(**query)


class UserFilter(InputFilter):
    parameter_name = "user_id"
    title = "User ID:"

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        return queryset.filter(user_id=term)


@admin.register(HistoricalPaymentCardAccount)
class HistoricalPaymentCardAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "instance_id",
        "user_id",
        "channel",
        "created",
        "change_type",
        "change_details",
    )
    search_fields = ("created",)
    list_filter = (
        PaymentCardAccountFilter,
        UserFilter,
        "channel",
        "change_type",
        ("created", DateTimeRangeFilter),
    )
    readonly_fields = ('created',)


@admin.register(HistoricalPaymentCardAccountEntry)
class HistoricalPaymentCardAccountEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "instance_id",
        "user_id",
        "payment_card_account_id",
        "channel",
        "change_type",
        "created",
        "change_details",
    )
    search_fields = ("instance_id", "created")
    list_filter = (
        PaymentCardAccountFilter,
        UserFilter,
        "channel",
        "change_type",
        ("created", DateTimeRangeFilter),
    )
    readonly_fields = ('created',)


@admin.register(HistoricalSchemeAccount)
class HistoricalSchemeAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "instance_id",
        "user_id",
        "channel",
        "journey",
        "change_type",
        "created",
        "change_details",
    )
    search_fields = ("created",)
    list_filter = (
        SchemeAccountFilter,
        UserFilter,
        "journey",
        "channel",
        "change_type",
        ("created", DateTimeRangeFilter),
    )
    readonly_fields = ('created',)


@admin.register(HistoricalSchemeAccountEntry)
class HistoricalSchemeAccountEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "instance_id",
        "user_id",
        "scheme_account_id",
        "channel",
        "change_type",
        "created",
        "change_details",
    )
    search_fields = ("instance_id", "created")
    list_filter = (
        SchemeAccountFilter,
        UserFilter,
        "channel",
        "change_type",
        ("created", DateTimeRangeFilter),
    )
    readonly_fields = ('created',)

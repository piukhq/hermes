from django.contrib import admin
from django.contrib.admin import DateFieldListFilter

from common.admin import InputFilter
from history.models import (
    HistoricalPaymentCardAccount,
    HistoricalSchemeAccount,
    HistoricalPaymentCardAccountEntry,
    HistoricalSchemeAccountEntry,
)


# TODO might be a good idea to capture and add things like Scheme and PaymentCard to the HistoricalTables
# TODO might be better to add a custom name to the Entry tables to the instance id to avoid confusion


class PaymentCardAccountFilter(InputFilter):
    parameter_name = 'payment_card_account_id'
    title = 'Payment Card Account ID:'

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        return queryset.filter(instance_id=term)


class SchemeAccountFilter(InputFilter):
    parameter_name = 'scheme_account_id'
    title = 'Scheme Account ID:'

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        return queryset.filter(instance_id=term)


class UserFilter(InputFilter):
    parameter_name = 'user_id'
    title = 'User ID:'

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        return queryset.filter(user_id=term)


@admin.register(HistoricalPaymentCardAccount)
class HistoricalPaymentCardAccountAdmin(admin.ModelAdmin):
    list_display = ("id", "instance_id", "user_id", "channel", "created", "change_type", "change_details")
    search_fields = ("created",)
    list_filter = (
        PaymentCardAccountFilter,
        UserFilter,
        "channel",
        "change_type",
        ("created", DateFieldListFilter)
    )


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
    search_fields = ("instance_id", "user_id", "payment_card_account_id", "created")
    list_filter = ("channel", "change_type")


@admin.register(HistoricalSchemeAccount)
class HistoricalSchemeAccountAdmin(admin.ModelAdmin):
    list_display = ("id", "instance_id", "user_id", "channel", "journey", "change_type", "created", "change_details")
    search_fields = ("created", )
    list_filter = (
        SchemeAccountFilter,
        UserFilter,
        "journey",
        "channel",
        "change_type",
        ("created", DateFieldListFilter)
    )


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
    search_fields = ("instance_id", "user_id", "scheme_account_id", "created")
    list_filter = ("channel", "change_type")

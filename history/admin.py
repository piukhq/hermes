from django.contrib import admin
from rangefilter.filter import DateTimeRangeFilter
from history.enums import HistoryModel

from common.admin import InputFilter
from history.models import (
    HistoricalPaymentCardAccount,
    HistoricalSchemeAccount,
    HistoricalPaymentCardAccountEntry,
    HistoricalSchemeAccountEntry,
    HistoricalCustomUser,
    HistoricalVopActivation,
    HistoricalPaymentCardSchemeEntry,
)


class PaymentCardAccountFilter(InputFilter):
    parameter_name = "payment_card_account_id"
    title = "Payment Card Account ID:"

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        if queryset.model.__name__ == HistoryModel.PAYMENT_CARD_ACCOUNT.model_name:
            query = {"instance_id": term}
        else:
            query = {"payment_card_account_id": term}

        return queryset.filter(**query)


class SchemeAccountFilter(InputFilter):
    parameter_name = "scheme_account_id"
    title = "Scheme Account ID:"

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        if queryset.model.__name__ == HistoryModel.SCHEME_ACCOUNT.model_name:
            query = {"instance_id": term}
        else:
            query = {"scheme_account_id": term}

        return queryset.filter(**query)


class SchemeFilter(InputFilter):
    parameter_name = "scheme_id"
    title = "Scheme ID:"

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        return queryset.filter(scheme_id=term)


class UserFilter(InputFilter):
    parameter_name = "user_id"
    title = "User ID:"

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        if queryset.model.__name__ == HistoryModel.CUSTOM_USER.model_name:
            query = {"instance_id": term}
        else:
            query = {"user_id": term}

        return queryset.filter(**query)


@admin.register(HistoricalCustomUser)
class HistoricalCustomUserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "instance_id",
        "email",
        "external_id",
        "channel",
        "created",
        "change_type",
    )
    search_fields = ("instance_id", "email", "external_id", "created")
    list_filter = (
        UserFilter,
        "channel",
        "change_type",
        ("created", DateTimeRangeFilter),
    )
    readonly_fields = ("created",)


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
    search_fields = ("instance_id", "created")
    list_filter = (
        PaymentCardAccountFilter,
        UserFilter,
        "channel",
        "change_type",
        ("created", DateTimeRangeFilter),
    )
    readonly_fields = ("created",)


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
    )
    search_fields = ("instance_id", "created")
    list_filter = (
        PaymentCardAccountFilter,
        UserFilter,
        "channel",
        "change_type",
        ("created", DateTimeRangeFilter),
    )
    readonly_fields = ("created",)


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
    search_fields = ("instance_id", "created")
    list_filter = (
        SchemeAccountFilter,
        UserFilter,
        "journey",
        "channel",
        "change_type",
        ("created", DateTimeRangeFilter),
    )
    readonly_fields = ("created",)


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
    )
    search_fields = ("instance_id", "created")
    list_filter = (
        SchemeAccountFilter,
        UserFilter,
        "channel",
        "change_type",
        ("created", DateTimeRangeFilter),
    )
    readonly_fields = ("created",)


@admin.register(HistoricalVopActivation)
class HistoricalVopActivationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "instance_id",
        "user_id",
        "channel",
        "payment_card_account_id",
        "scheme_id",
        "change_type",
        "created",
        "change_details",
    )
    search_fields = ("instance_id", "created")
    list_filter = (
        UserFilter,
        PaymentCardAccountFilter,
        SchemeFilter,
        "channel",
        "change_type",
        ("created", DateTimeRangeFilter),
    )
    readonly_fields = ("created",)


@admin.register(HistoricalPaymentCardSchemeEntry)
class HistoricalPaymentCardSchemeEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "instance_id",
        "user_id",
        "channel",
        "payment_card_account_id",
        "scheme_account_id",
        "change_type",
        "created",
        "change_details",
    )
    search_fields = ("instance_id", "created")
    list_filter = (
        UserFilter,
        PaymentCardAccountFilter,
        SchemeAccountFilter,
        "channel",
        "change_type",
        ("created", DateTimeRangeFilter),
    )
    readonly_fields = ("created",)

from django.contrib import admin

from history.models import (
    HistoricalPaymentCardAccount,
    HistoricalSchemeAccount,
    HistoricalPaymentCardAccountEntry,
    HistoricalSchemeAccountEntry,
)


# TODO might be a good idea to capture and add things like Scheme and PaymentCard to the HistoricalTables
# TODO might be better to add a custom name to the Entry tables to the instance id to avoid confusion


@admin.register(HistoricalPaymentCardAccount)
class HistoricalPaymentCardAccountAdmin(admin.ModelAdmin):
    list_display = ("id", "instance_id", "user_id", "channel", "created", "change_type", "change_details")
    search_fields = ("instance_id", "user_id", "created")
    list_filter = ("channel", "change_type")


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
    list_display = ("id", "instance_id", "user_id", "channel", "change_type", "created", "change_details")
    search_fields = ("instance_id", "user_id", "created")
    list_filter = ("channel", "change_type")


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

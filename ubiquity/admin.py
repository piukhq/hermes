from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html
from rangefilter.filters import DateTimeRangeFilter

from common.admin import InputFilter
from payment_card.admin import titled_filter
from scheme.admin import CacheResetAdmin
from ubiquity.models import MembershipPlanDocument, PaymentCardSchemeEntry, PllUserAssociation, VopActivation


@admin.register(PaymentCardSchemeEntry)
class PaymentCardSchemeEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "active_link",
        "payment_card_account_link",
        "scheme_account_link",
        "pcard_status",
        "pcard_deleted",
        "mcard_deleted",
    )
    search_fields = (
        "payment_card_account__id",
        "scheme_account__id",
        "payment_card_account__pan_start",
        "payment_card_account__pan_end",
        "payment_card_account__token",
        "scheme_account__scheme__name",
        "payment_card_account__payment_card__name",
    )

    list_filter = (
        "active_link",
        ("payment_card_account__issuer__name", titled_filter("payment card issuer")),
        ("payment_card_account__is_deleted", titled_filter("payment card is deleted")),
        ("scheme_account__is_deleted", titled_filter("membership card is deleted")),
        ("payment_card_account__status", titled_filter("payment card status")),
        ("payment_card_account__payment_card__name", titled_filter("payment card")),
        ("scheme_account__scheme", titled_filter("membership card")),
    )
    raw_id_fields = (
        "payment_card_account",
        "scheme_account",
    )

    readonly_fields = ("active_link",)

    def payment_card_account_link(self, obj):
        return format_html(
            '<a href="/admin/payment_card/paymentcardaccount/{0}/change/">' "pcard id = {0} - No. {1}...{2}</a>",
            obj.payment_card_account.id,
            obj.payment_card_account.pan_start,
            obj.payment_card_account.pan_end,
        )

    def scheme_account_link(self, obj):
        return format_html(
            '<a href="/admin/scheme/schemeaccount/{0}/change/">mcard id = {0}</a>', obj.scheme_account.id
        )

    def pcard_status(self, obj):
        return obj.payment_card_account.status_name

    def mcard_status(self, obj):
        return obj.scheme_account.status_name

    def mcard_deleted(self, obj):
        return obj.scheme_account.is_deleted

    def pcard_deleted(self, obj):
        return obj.payment_card_account.is_deleted

    pcard_deleted.boolean = True
    mcard_deleted.boolean = True


class PllFilter(InputFilter):
    parameter_name = "pll_id_contains"
    title = "Pll User Association ID Containing:"

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return
        query = Q(pll__id__icontains=term)
        return queryset.filter(query)


class UserFilter(InputFilter):
    parameter_name = "user_id_contains"
    title = "User ID Containing:"

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return
        query = Q(user__id__icontains=term)
        return queryset.filter(query)


class UserEmailFilter(InputFilter):
    parameter_name = "user_email_contains"
    title = "User Email Containing:"

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return
        query = Q(user__email__icontains=term)
        return queryset.filter(query)


class PaymentAccountTokenFilter(InputFilter):
    parameter_name = "token_contains"
    title = "PLL Card token Containing:"

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return
        query = Q(pll__payment_card_account__token__icontains=term)
        return queryset.filter(query)


class PaymentAccountFingerFilter(InputFilter):
    parameter_name = "fingerprint_contains"
    title = "PLL Card fingerprint Containing:"

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return
        query = Q(pll__payment_card_account__fingerprint__icontains=term)
        return queryset.filter(query)


@admin.register(PllUserAssociation)
class PllUserAssociationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "pll_link", "pll_link_state", "state", "slug", "created", "updated")
    search_fields = (
        "id",
        "pll__payment_card_account__id",
        "pll__scheme_account__id",
    )

    list_filter = (
        "pll__active_link",
        "state",
        "slug",
        UserFilter,
        UserEmailFilter,
        PllFilter,
        PaymentAccountTokenFilter,
        PaymentAccountFingerFilter,
        ("created", DateTimeRangeFilter),
        ("updated", DateTimeRangeFilter),
        ("pll__active_link", titled_filter("active_link")),
        ("pll__payment_card_account__issuer__name", titled_filter("payment card issuer")),
        ("pll__payment_card_account__is_deleted", titled_filter("payment card account is deleted")),
        ("pll__scheme_account__is_deleted", titled_filter("membership card is deleted")),
        ("pll__payment_card_account__status", titled_filter("payment card status")),
        ("pll__payment_card_account__payment_card__name", titled_filter("payment card")),
        ("pll__scheme_account__scheme", titled_filter("Loyalty Plan")),
    )

    raw_id_fields = ("user", "pll")

    readonly_fields = (
        # "user",
        # "pll",
        # "state",
        # "slug"
    )

    def pll_link(self, obj):
        return format_html(
            '<a href="/admin/ubiquity/paymentcardschemeentry/?id={0}">' "{0}</a>",
            obj.pll.id,
        )

    def pll_link_state(self, obj):
        return obj.pll.active_link


@admin.register(MembershipPlanDocument)
class MembershipPlanDocumentAdmin(CacheResetAdmin):
    list_display = ("name", "scheme", "url", "order", "display", "checkbox")
    search_fields = ("name", "scheme__name", "url", "display")
    list_filter = ("scheme",)
    raw_id_fields = ("scheme",)


@admin.register(VopActivation)
class VopActivationAdmin(admin.ModelAdmin):
    list_display = ("scheme", "payment_card_account", "pay_card_id", "status", "activation_id")
    search_fields = (
        "scheme__name",
        "scheme__slug",
        "payment_card_account__psp_token",
        "payment_card_account__pan_start",
        "payment_card_account__pan_end",
        "payment_card_account__id",
        "status",
    )
    raw_id_fields = ("scheme", "payment_card_account")
    list_filter = ("status",)

    def pay_card_id(self, obj):
        return obj.payment_card_account.id

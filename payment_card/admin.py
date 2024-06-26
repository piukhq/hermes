import arrow
from django.contrib import admin
from django.utils.html import format_html

from history.utils import HistoryAdmin
from payment_card import models
from ubiquity.models import PaymentCardAccountEntry


@admin.register(models.PaymentCard)
class PaymentCardAdmin(admin.ModelAdmin):
    list_display = ("name", "id", "is_active")
    list_filter = ("is_active",)


admin.site.register(models.Issuer)


@admin.register(models.PaymentCardImage)
class PaymentCardImageAdmin(admin.ModelAdmin):
    list_display = ("payment_card", "description", "status", "start_date", "end_date", "created")
    list_filter = ("payment_card", "status", "created")
    search_fields = ("payment_card__name", "description")
    raw_id_fields = ("payment_card",)

    def get_queryset(self, request):
        qs = self.model.all_objects.get_queryset()
        ordering = self.ordering or ()
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


def titled_filter(title):
    class Wrapper(admin.RelatedFieldListFilter):
        def __new__(cls, *args, **kwargs):
            instance = admin.RelatedFieldListFilter.create(*args, **kwargs)
            instance.title = title
            return instance

    return Wrapper


@admin.register(models.PaymentCardAccount)
class PaymentCardAccountAdmin(HistoryAdmin):
    def obfuscated_hash(self, obj):
        if obj.hash:
            obf_hash = "*" * (len(obj.hash) - 4) + obj.hash[-4:]
        else:
            obf_hash = "N/A"

        return obf_hash

    obfuscated_hash.short_description = "Hash"
    list_display = ("payment_card", "status", "user_email", "pan_start", "pan_end", "is_deleted", "created", "updated")
    list_filter = (
        ("payment_card__name", titled_filter("payment card")),
        "status",
        ("issuer__name", titled_filter("issuer")),
        "is_deleted",
    )
    readonly_fields = ("obfuscated_hash", "token", "psp_token", "PLL_consent", "user_email", "created", "updated")
    search_fields = (
        "pan_start",
        "pan_end",
        "psp_token",
        "fingerprint",
        "paymentcardaccountentry__user__email",
        "hash",
        "agent_data",
        "token",
        "id",
        "created",
    )
    exclude = ("consent", "hash")

    def user_email(self, obj):
        user_list = [
            format_html(
                '<a href="/admin/user/customuser/{}/change/">{}</a>',
                assoc.user.id,
                assoc.user.email if assoc.user.email else assoc.user.uid,
            )
            for assoc in PaymentCardAccountEntry.objects.filter(payment_card_account=obj.id)
        ]
        return format_html("</br>".join(user_list))

    user_email.allow_tags = True

    def PLL_consent(self, obj):  # noqa: N802
        when = arrow.get(obj.consent["timestamp"]).format("HH:mm DD/MM/YYYY")
        return "Date Time: {} \nCoordinates: {}, {}".format(when, obj.consent["latitude"], obj.consent["longitude"])


@admin.register(models.PaymentCardAccountImage)
class PaymentCardAccountImageAdmin(admin.ModelAdmin):
    list_display = ("payment_card", "description", "status", "start_date", "end_date", "created")
    list_filter = ("payment_card", "status", "created")
    search_fields = ("payment_card__name", "description")
    raw_id_fields = ("payment_card_accounts",)

    def get_queryset(self, request):
        qs = self.model.all_objects.get_queryset()
        ordering = self.ordering or ()
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


@admin.register(models.ProviderStatusMapping)
class ProviderStatusMappingAdmin(admin.ModelAdmin):
    list_display = ("provider", "provider_status_code", "bink_status_code")
    list_filter = ("provider", "bink_status_code")
    search_fields = ("provider_status_code", "bink_status_code")


@admin.register(models.AuthTransaction)
class AuthTransactionAdmin(admin.ModelAdmin):
    list_display = ("payment_card_account", "time", "amount", "mid", "third_party_id")
    search_fields = ("payment_card_account", "mid", "third_party_id")


class PaymentCardUserAssociation(PaymentCardAccountEntry):
    """
    We are using a proxy model in admin for sole purpose of using an appropriate table name which is then listed
    in schemes and not ubiquity.  Using SchemeAccountEntry directly adds an entry in Ubiquity section called
    SchemeAccountEntry which would confuse users as it is not ubiquity specific and is not a way of entering
    scheme accounts ie it used to associate a scheme with a user.

    """

    class Meta:
        proxy = True
        verbose_name = "Payment Card Account to User Association"
        verbose_name_plural = "".join([verbose_name, "s"])


@admin.register(PaymentCardUserAssociation)
class PaymentCardUserAssociationAdmin(HistoryAdmin):
    list_display = (
        "payment_card_account_id",
        "user_id",
        "payment_card_account",
        "user",
        "payment_card_account_link",
        "user_link",
        "card_status",
        "card_is_deleted",
        "card_created",
    )
    search_fields = (
        "payment_card_account__pan_start",
        "payment_card_account__pan_end",
        "payment_card_account__token",
        "user__email",
        "user__external_id",
    )

    list_filter = (
        ("payment_card_account__payment_card__name", titled_filter("payment card")),
        "payment_card_account__status",
        ("payment_card_account__issuer__name", titled_filter("issuer")),
        "payment_card_account__is_deleted",
    )
    raw_id_fields = ("payment_card_account", "user")

    def payment_card_account_id(self, obj):
        return obj.payment_card_account.id

    def user_id(self, obj):
        return obj.user.id

    def payment_card_account_link(self, obj):
        return format_html(
            '<a href="/admin/payment_card/paymentcardaccount/{0}/change/">card (id{0}) No. {1}...{2}</a>',
            obj.payment_card_account.id,
            obj.payment_card_account.pan_start,
            obj.payment_card_account.pan_end,
        )

    def user_link(self, obj):
        user_name = obj.user.external_id
        if not user_name:
            user_name = obj.user.get_username()
        if not user_name:
            user_name = obj.user.email
        return format_html('<a href="/admin/user/customuser/{}/change/">{}</a>', obj.user.id, user_name)

    def card_status(self, obj):
        return obj.payment_card_account.status_name

    def card_created(self, obj):
        return obj.payment_card_account.created

    def card_is_deleted(self, obj):
        return obj.payment_card_account.is_deleted

    card_is_deleted.boolean = True


@admin.register(models.PaymentAudit)
class PaymentAuditAdmin(admin.ModelAdmin):
    list_display = (
        "scheme_account",
        "user_id",
        "transaction_ref",
        "transaction_token",
        "status",
        "created_on",
        "modified_on",
    )
    search_fields = (
        "scheme_account__id",
        "user_id",
        "scheme_account__scheme__name",
        "transaction_ref",
        "transaction_token",
        "status",
        "payment_card_hash",
        "payment_card_id",
    )
    readonly_fields = (
        "user_id",
        "scheme_account",
        "transaction_ref",
        "transaction_token",
        "created_on",
        "modified_on",
        "void_attempts",
        "status",
        "payment_card_hash",
        "payment_card_id",
    )


@admin.register(models.VopMerchantGroup)
class VopMerchantGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "offer_id", "group_name", "default")
    readonly_fields = ("default",)
    search_fields = ("offer_id", "group_name")
    fieldsets = (
        (
            None,
            {
                "fields": ("offer_id", "group_name"),
                "description": (
                    "If these fields are updated a restart of the pods is required "
                    "for the changes to be reflected in Hermes."
                ),
            },
        ),
    )

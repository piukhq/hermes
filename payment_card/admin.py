from typing import TYPE_CHECKING

import arrow
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from history.utils import HistoryAdmin
from payment_card import models
from periodic_retry.models import PeriodicRetry, PeriodicRetryStatus, RetryTaskList
from periodic_retry.tasks import PeriodicRetryHandler
from ubiquity.models import PaymentCardAccountEntry

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest


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
    actions = ["retry_enrolment"]

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

    def PLL_consent(self, obj):
        when = arrow.get(obj.consent["timestamp"]).format("HH:mm DD/MM/YYYY")
        return f'Date Time: {when} \nCoordinates: {obj.consent["latitude"]}, {obj.consent["longitude"]}'

    def _process_valid_payment_card_accounts(
        self, request: "HttpRequest", pcas: "QuerySet", retry_handler: PeriodicRetryHandler
    ) -> tuple[int, list[int]]:
        requeued: int = 0
        non_failed_retries: list[int] = []
        pca: models.PaymentCardAccount
        for pca in pcas:
            try:
                periodic_retry = PeriodicRetry.objects.get(
                    task_group=RetryTaskList.METIS_REQUESTS,
                    data__context__card_id=pca.id,
                )
            except PeriodicRetry.DoesNotExist:
                retry_handler.new(
                    "payment_card.metis",
                    "retry_enrol",
                    context={"card_id": int(pca.id)},
                    retry_kwargs={
                        "max_retry_attempts": 10,
                        "results": [{"caused_by": "Manual retry"}],
                        "status": PeriodicRetryStatus.REQUIRED,
                    },
                )
                requeued += 1
            except PeriodicRetry.MultipleObjectsReturned:
                self.message_user(
                    request,
                    f"Found multiple PeriodicRetryObjects objecs for PaymentCardAccount with id: {pca.id}",
                    level=messages.ERROR,
                )
            else:
                if periodic_retry.status != PeriodicRetryStatus.FAILED:
                    non_failed_retries.append(pca.id)
                    continue

                periodic_retry.max_retry_attempts += 10
                periodic_retry.next_retry_after = timezone.now()
                periodic_retry.status = PeriodicRetryStatus.REQUIRED
                periodic_retry.save(update_fields=["max_retry_attempts", "next_retry_after", "status"])
                retry_handler.set_task(
                    periodic_retry,
                    module_name="payment_card.metis",
                    function_name="retry_enrol",
                    data=periodic_retry.data,
                )
                requeued += 1
        return requeued, non_failed_retries

    @admin.action(description="Retry enrolment")
    def retry_enrolment(self: admin.ModelAdmin, request: "HttpRequest", queryset: "QuerySet") -> None:
        allowed_group_names = ["Scripts Run and Correct", "Scripts Run Only"]
        if not request.user.is_superuser and all(
            group_name not in request.user.groups.all().values_list("name", flat=True)
            for group_name in allowed_group_names
        ):
            self.message_user(
                request,
                f"Only super users and members of the following Groups can use this tool: {allowed_group_names}",
                level=messages.ERROR,
            )
            return

        valid_statuses = {models.PaymentCardAccount.PROVIDER_SERVER_DOWN, models.PaymentCardAccount.UNKNOWN}
        valid_status_descs = {
            f"{desc}" for status, desc in models.PaymentCardAccount.STATUSES if status in valid_statuses
        }
        if invalid_pcas := queryset.exclude(status__in=valid_statuses):
            self.message_user(
                request,
                f"PaymentCardAccounts with invalid status submitted: "
                f"{', '.join([str(ipca.id) for ipca in invalid_pcas])}. "
                f"Only PaymentCardAccounts with the following statuses can be attempted: "
                f"{valid_status_descs}",
                level=messages.ERROR,
            )
        valid_pcas = queryset.filter(status__in=valid_statuses)
        retry_handler = PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS)
        requeued: int = 0
        non_failed_retries: list[int] = []
        requeued, non_failed_retries = self._process_valid_payment_card_accounts(request, valid_pcas, retry_handler)

        if requeued:
            self.message_user(request, f"Requeued {requeued} PaymentCardAccount enrolments")
        if non_failed_retries:
            self.message_user(
                request,
                "The following PaymentCardAccounts where found to have PeriodicRetrys in non-FAILED state: "
                f"{non_failed_retries}. Ignoring these.",
                level=messages.WARNING,
            )


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

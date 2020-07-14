from django.contrib import admin

from .models import PeriodicRetry
from payment_card.models import PaymentCardAccount
from ubiquity.models import PaymentCardSchemeEntry, VopActivation
from periodic_retry.models import PeriodicRetryStatus, RetryTaskList
from periodic_retry.tasks import PeriodicRetryHandler


def add_visa_active_user(modeladmin, request, queryset):
    payment_card_account = PaymentCardAccount.objects.filter(status=1, payment_card_account__slug='visa')
    for visa_card in payment_card_account:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'payment_card.metis', "retry_enrol",
            context={"card_id": visa_card.id},
            retry_kwargs={"max_retry_attempts": 1,
                          "results": [{"caused_by": "migration script"}],
                          "status": PeriodicRetryStatus.PENDING
                          }
        )


add_visa_active_user.short_description = "Add Visa Enrolments"


def enrol_visa_user(modeladmin, request, queryset):
    queryset.update(status=0)


enrol_visa_user.short_description = "Trigger Retry"


def activate_visa_user(modeladmin, request, queryset):
    payment_card_scheme = PaymentCardSchemeEntry.objects.filter(payment_card_account__payment_card__slug='visa',
                                                                active_link=True)
    for entry in payment_card_scheme:
        vop_activation, created = VopActivation.objects.get_or_create(
            payment_card_account=entry.payment_card_account,
            scheme=entry.scheme_account.scheme,
            defaults={'activation_id': "", "status": VopActivation.ACTIVATING}
        )

        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'ubiquity.tasks', "retry_activation",
            context={"activation_id": vop_activation.id},
            retry_kwargs={"max_retry_attempts": 1,
                          "results": [{"caused_by": "migration script"}],
                          "status": PeriodicRetryStatus.PENDING
                          }
        )


activate_visa_user.short_description = "Add Visa Activations"


@admin.register(PeriodicRetry)
class PeriodicRetryAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_group', 'function', 'status', 'retry_count', 'max_retry_attempts', 'next_retry_after',
                    'created_on',)
    readonly_fields = ('created_on', 'modified_on',)
    search_fields = ('id', 'status', 'task_group', 'function', 'module',)
    actions = [enrol_visa_user, add_visa_active_user, activate_visa_user]

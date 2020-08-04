import arrow
from django.contrib import admin
from django.db import IntegrityError
from payment_card.models import PaymentCardAccount, PaymentCard
from periodic_retry.models import PeriodicRetryStatus, RetryTaskList
from periodic_retry.tasks import PeriodicRetryHandler
from ubiquity.models import PaymentCardSchemeEntry, VopActivation

from .models import PeriodicRetry


def caution_line_break(modeladmin, request, queryset):
    pass


caution_line_break.short_description = "--- Caution one time Data Migration:"


def add_visa_enrolments(modeladmin, request, queryset):
    visa_card = PaymentCard.objects.get(slug='visa')
    visa_card.token_method = PaymentCard.TokenMethod.COPY
    visa_card.save()
    active_visa_accounts = PaymentCardAccount.objects.filter(status=1, payment_card__slug='visa')
    for visa_account in active_visa_accounts:
        visa_account.token = visa_account.psp_token
        visa_account.save(update_fields=["token"])
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'payment_card.metis', "retry_enrol",
            context={"card_id": visa_account.id},
            retry_kwargs={"max_retry_attempts": 1,
                          "results": [{"caused_by": "migration script"}],
                          "status": PeriodicRetryStatus.PENDING
                          }
        )


add_visa_enrolments.short_description = "Add Visa Enrolments"


def trigger_retry(modeladmin, request, queryset):
    count = 0
    for entry in queryset:
        count += 1
        update_time = arrow.utcnow().shift(seconds=int(count/5))

        if entry.status != PeriodicRetryStatus.SUCCESSFUL:
            # Never retry a successful response
            if entry.max_retry_attempts - entry.retry_count < 1:
                entry.max_retry_attempts = entry.retry_count + 1

            entry.next_retry_after = update_time.datetime
            entry.status = PeriodicRetryStatus.REQUIRED
            entry.save()


trigger_retry.short_description = "Trigger Retry"


def activate_visa_user(modeladmin, request, queryset):
    linked_visa_cards = PaymentCardSchemeEntry.objects.filter(
        payment_card_account__payment_card__slug='visa', active_link=True
    )
    for link in linked_visa_cards:

        try:
            vop_activation, created = VopActivation.objects.get_or_create(
                payment_card_account=link.payment_card_account,
                scheme=link.scheme_account.scheme,
                defaults={'activation_id': "", "status": VopActivation.ACTIVATING}
            )

            if created:
                # If we have an activation record it implies the user has already migrated
                # and should either have activated successfully or already have a retry entry
                data = {
                    'payment_token': vop_activation.payment_card_account.psp_token,
                    'partner_slug': 'visa',
                    'merchant_slug': vop_activation.scheme.slug
                }

                PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
                    'ubiquity.tasks', "retry_activation",
                    context={"activation_id": vop_activation.id, "post_data": data},
                    retry_kwargs={"max_retry_attempts": 1,
                                  "results": [{"caused_by": "migration script"}],
                                  "status": PeriodicRetryStatus.PENDING
                                  }
                )

        except IntegrityError:
            # Unlikey to occur in migration unless command issued on multiple pods - no error if already activated
            pass


activate_visa_user.short_description = "Add Visa Activations"


@admin.register(PeriodicRetry)
class PeriodicRetryAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_group', 'function', 'status', 'retry_count', 'max_retry_attempts', 'next_retry_after',
                    'created_on',)
    readonly_fields = ('created_on', 'modified_on',)
    search_fields = ('id', 'status', 'task_group', 'function', 'module',)
    actions = [trigger_retry, caution_line_break, add_visa_enrolments, activate_visa_user]

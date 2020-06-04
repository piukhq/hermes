from typing import Iterable

import requests
from celery import shared_task
from django.conf import settings
from periodic_retry.models import RetryTaskList
from periodic_retry.tasks import PeriodicRetryHandler
from ubiquity.models import PaymentCardSchemeEntry


def vop_check_scheme(scheme_account):
    """ This method finds all the visa payment cards linked to this scheme account with undefined VOP status
    """
    # Must import here to avoid circular imports in future consider moving status definitions outside of model
    from payment_card.models import PaymentCardAccount

    entries = PaymentCardSchemeEntry.objects.filter(
        scheme_account=scheme_account,
        payment_card_account__status=PaymentCardAccount.ACTIVE,
        payment_card_account__payment_card__slug="visa",
        vop_link=PaymentCardSchemeEntry.UNDEFINED
    )

    if entries:
        vop_activate(entries)


def vop_activate(entries: Iterable[PaymentCardSchemeEntry]):

    for entry in entries:
        entry.vop_link = PaymentCardSchemeEntry.ACTIVATING
        entry.save()

        body = {
            'payment_token': entry.payment_card_account.psp_token,
            'partner_slug': entry.scheme_account.scheme.slug,
            'association_id': entry.id,
            'payment_card_account_id': entry.payment_card_account.id,
            'scheme_account_id': entry.scheme_account.id
        }
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'hermes.vop_tasks', 'try_activation',
            context={"entry_id": entry.id, "body": body},
            retry_kwargs={"max_retry_attempts": 100}
        )
        # send_activation.delay(entry, data)


def deactivate_delete_link(entry: PaymentCardSchemeEntry):
    if entry.payment_card_account.payment_card.slug == "visa":
        send_deactivation.delay(entry)
    else:
        entry.delete()


def deactivate_vop_list(entries: PaymentCardSchemeEntry):
    # pass list and send to deactivate.
    for entry in entries:
        send_deactivation.delay(entry)


def try_activation(data):
    retry_obj = data["periodic_retry_obj"]
    print(data['context'], retry_obj.next_retry_after, retry_obj.retry_count)

    #if (some_success_case):
        #handler.done()

    retry_obj.results += ["Retry results"]


@shared_task
def send_activation(entry: PaymentCardSchemeEntry, data: dict):
    rep = requests.post(settings.METIS_URL + '/visa/activate/',
                        json=data,
                        headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                                 'Content-Type': 'application/json'})
    if rep.status_code == 201:
        entry.vop_link = PaymentCardSchemeEntry.ACTIVATED
        entry.save()


@shared_task
def send_deactivation(entry: PaymentCardSchemeEntry):
    entry.vop_link = PaymentCardSchemeEntry.DEACTIVATING
    entry.save()
    data = {
        'payment_token': entry.payment_card_account.psp_token,
        'partner_slug': entry.scheme_account.scheme.slug,
        'association_id': entry.id,
        'payment_card_account_id': entry.payment_card_account.id,
        'scheme_account_id': entry.scheme_account.id
    }
    retry_count = 3
    while retry_count:
        rep = requests.post(settings.METIS_URL + '/visa/deactivate/',
                            json=data,
                            headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                                     'Content-Type': 'application/json'})
        retry_count -= 1
        if rep.status_code == 201:
            retry_count = 0
    entry.delete()

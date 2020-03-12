
from ubiquity.models import PaymentCardSchemeEntry
from ubiquity.tasks import visa_enrol


def vop_check_payment(scheme_account):
    """ This function finds all the visa payment cards linked this scheme account with undefined VOP status

    :param scheme_account: Scheme account which has just turned active
    :return:
    """

    entries = PaymentCardSchemeEntry.objects.filter(
        scheme_account=scheme_account,
        payment_card_account__payment_card__slug="visa",
        vop_link=PaymentCardSchemeEntry.UNDEFINED
    )

    vop_enroll(entries)


def vop_check_schemeaccount(payment_card_account):
    """ This function finds all the merchant accounts linked to this payment card account with undefined VOP status

    :param payment_card_account:
    :return:
    """
    entries = PaymentCardSchemeEntry.objects.filter(
        payment_card_account=payment_card_account,
        payment_card_account__payment_card__slug="visa",
        vop_link=PaymentCardSchemeEntry.UNDEFINED
    )

    vop_enroll(entries)


def vop_enroll(entries):
    for entry in entries:
        entry.vop_link = PaymentCardSchemeEntry.ACTIVATING
        entry.save()

        data = {
            'payment_token': entry.payment_card_account.psp_token,
            'merchant_slug': entry.scheme_account.scheme.slug,
            'association_id': entry.id,
            'payment_card_account_id': entry.payment_card_account.id,
            'scheme_account_id': entry.scheme_account.id
        }

        visa_enrol.delay(data)

from ubiquity.models import PaymentCardSchemeEntry
from ubiquity.tasks import visa_enrol


def vop_check_payment(scheme_account):
    """ This function finds the payment cards linked to the scheme account and if VOP

    :param SchemeAccount: Scheme account which has just turned active
    :return:
    """
    cards = PaymentCardSchemeEntry.objects.filter(scheme_account=scheme_account,
                                                  payment_card_account__payment_card__slug="visa",
                                                  vop_link=PaymentCardSchemeEntry.VOP_STATUS.undefined)
    visa_enrol.delay(cards)


def vop_check_schemeaccount(payment_card_account):
    cards = PaymentCardSchemeEntry.objects.filter(payment_card_account=payment_card_account,
                                                  payment_card_account__payment_card__slug="visa",
                                                  vop_link=PaymentCardSchemeEntry.VOP_STATUS.undefined)

    visa_enrol.delay(cards)


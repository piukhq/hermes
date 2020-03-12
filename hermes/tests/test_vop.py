2
from ubiquity.models import PaymentCardSchemeEntry
from scheme.models import SchemeAccount
from payment_card.models import PaymentCardAccount



def test_my_user():

    #cards = PaymentCardAccount.objects.filter(PaymentCardSchemeEntry__op_link=PaymentCardSchemeEntry.UNDEFINED)

    card_entries = PaymentCardSchemeEntry.objects.filter(id=4)


    print(card_entries)

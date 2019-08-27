from django.test import TestCase
from django.conf import settings
import httpretty

from payment_card.metis import enrol_existing_payment_card
from payment_card.models import PaymentCard
from payment_card.tests.factories import PaymentCardAccountFactory


class TestMetisClient(TestCase):
    @httpretty.activate
    def test_enrol_existing_payment_card(self):
        httpretty.register_uri(httpretty.POST, settings.METIS_URL + '/payment_service/payment_card/update', status=204)
        account = PaymentCardAccountFactory()
        account.payment_card.name = PaymentCard.MASTERCARD
        enrol_existing_payment_card(account)
        self.assertTrue(httpretty.has_request())

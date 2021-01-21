import httpretty
from django.conf import settings

from history.utils import GlobalMockAPITestCase
from payment_card.metis import enrol_existing_payment_card
from payment_card.models import PaymentCard
from payment_card.tests.factories import PaymentCardAccountFactory


class TestMetisClient(GlobalMockAPITestCase):
    @httpretty.activate
    def test_enrol_existing_payment_card(self):
        httpretty.register_uri(httpretty.POST, settings.METIS_URL + '/payment_service/payment_card/update', status=204)
        account = PaymentCardAccountFactory()
        account.payment_card.name = PaymentCard.MASTERCARD
        enrol_existing_payment_card(account, run_async=False)
        self.assertTrue(httpretty.has_request())

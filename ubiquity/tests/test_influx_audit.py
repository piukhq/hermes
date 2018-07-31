from rest_framework.test import APITestCase

from ubiquity.influx_audit import InfluxAudit
from ubiquity.tests.factories import (PaymentCardAccountEntryFactory, PaymentCardSchemeEntryFactory,
                                      SchemeAccountEntryFactory)


class TestResources(APITestCase):

    def setUp(self):
        payment_card_account_entry = PaymentCardAccountEntryFactory()
        scheme_account_entry = SchemeAccountEntryFactory(user=payment_card_account_entry.user)
        self.cards_link = PaymentCardSchemeEntryFactory(
            payment_card_account=payment_card_account_entry.payment_card_account,
            scheme_account=scheme_account_entry.scheme_account)
        self.audit = InfluxAudit()

    def test_influx_db_audit(self):
        self.audit.write_to_db(self.cards_link)

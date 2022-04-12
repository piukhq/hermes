from unittest.mock import patch

from django.test import TestCase

from history import data_warehouse
from scheme.tests.factories import SchemeAccountFactory
from user.tests.factories import (
    ClientApplicationBundleFactory,
    ClientApplicationFactory,
    OrganisationFactory,
    UserFactory,
)


class TestEventHandlers(TestCase):
    @classmethod
    def setUpClass(cls):
        organisation = OrganisationFactory(name="test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=organisation,
            name="set up client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")
        cls.mcard = SchemeAccountFactory()
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def TestRemoveLoyaltyCardEvent(self, mock_to_warehouse):
        data_warehouse.remove_loyalty_card_event(self.user, self.mcard)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.removed")
        self.assertEqual(data["origin"], "channel")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["main_answer"], self.mcard.main_answer)
        self.assertEqual(data["status"], self.mcard.status)

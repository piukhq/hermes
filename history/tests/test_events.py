from copy import deepcopy
from unittest.mock import patch

import arrow
from django.test import TestCase, override_settings

from history.data_warehouse import (
    add_auth_outcome,
    addauth_request_lc_event,
    auth_outcome,
    auth_request_lc_event,
    create_trusted_event,
    join_outcome,
    join_request_lc_event,
    register_lc_event,
    register_outcome,
    remove_loyalty_card_event,
)
from history.utils import clean_history_kwargs, set_history_kwargs, user_info
from payment_card.models import PaymentCardAccount
from scheme.models import SchemeAccount, SchemeBundleAssociation
from scheme.tests.factories import (
    SchemeAccountFactory,
    SchemeBundleAssociationFactory,
    SchemeFactory,
    UserConsentFactory,
    fake,
)
from ubiquity.models import AccountLinkStatus, PllUserAssociation, WalletPLLSlug, WalletPLLStatus
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory
from ubiquity.tests.test_linking import (
    add_payment_card_account_to_wallet,
    set_up_membership_card,
    set_up_payment_card,
    set_up_payment_card_account,
    set_up_scheme,
)
from user.tests.factories import (
    ClientApplicationBundleFactory,
    ClientApplicationFactory,
    OrganisationFactory,
    UserFactory,
)


def get_main_answer(scheme_account: SchemeAccount):
    return scheme_account.card_number or scheme_account.barcode or scheme_account.alt_main_answer


class TestRemoveLCEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")

        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)

        cls.scheme_acc_entry = SchemeAccountEntryFactory(scheme_account=cls.mcard, user=cls.user)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_remove_loyalty_card_event(self, mock_to_warehouse):
        remove_loyalty_card_event(self.scheme_acc_entry)

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
        self.assertEqual(data["main_answer"], self.mcard.alt_main_answer)
        self.assertEqual(data["status"], self.scheme_acc_entry.link_status)


class TestRegisterLCEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")

        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)
        cls.mcard_entry = SchemeAccountEntryFactory(scheme_account=cls.mcard, user=cls.user)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_register_lc_event(self, mock_to_warehouse):
        register_lc_event(self.mcard_entry, "test.auth.fake")

        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.register.request")
        self.assertEqual(data["origin"], "channel")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["main_answer"], self.mcard.alt_main_answer)


class TestJoinRequestLCEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")

        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)
        cls.mcard_entry = SchemeAccountEntryFactory(scheme_account=cls.mcard, user=cls.user)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_join_request_lc_event(self, mock_to_warehouse):
        join_request_lc_event(self.mcard_entry, "test.auth.fake")

        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.join.request")
        self.assertEqual(data["origin"], "channel")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)


class TestAAALCEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")

        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)
        cls.date_time = arrow.utcnow().isoformat()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_addauth_request_lc_event(self, mock_to_warehouse):
        addauth_request_lc_event(self.user, self.mcard, "test.auth.fake", date_time=self.date_time)

        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.addandauth.request")
        self.assertEqual(data["origin"], "channel")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["main_answer"], self.mcard.alt_main_answer)


class TestAuthRequestEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")

        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)
        cls.date_time = arrow.utcnow().isoformat()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_auth_request_lc_event(self, mock_to_warehouse):
        auth_request_lc_event(self.user, self.mcard, "test.auth.fake", date_time=self.date_time)

        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.auth.request")
        self.assertEqual(data["origin"], "channel")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["main_answer"], self.mcard.alt_main_answer)


class TestJoinSuccessEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")
        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)
        cls.mcard_entry = SchemeAccountEntryFactory(scheme_account=cls.mcard, user=cls.user)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_success_join(self, mock_to_warehouse):
        user_consents = [
            UserConsentFactory(user=self.user, scheme_account=self.mcard, scheme=self.scheme, value=True),
            UserConsentFactory(user=self.user, scheme_account=self.mcard, scheme=self.scheme, value=False),
        ]
        expected_consents = [
            {
                "slug": consent.slug,
                "response": consent.value,
            }
            for consent in user_consents
        ]

        join_outcome(True, self.mcard_entry)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.join.success")
        self.assertEqual(data["origin"], "merchant.callback")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["main_answer"], self.mcard.alt_main_answer)
        self.assertEqual(data["status"], self.mcard_entry.link_status)
        self.assertEqual(data["consents"], expected_consents)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_no_consents(self, mock_to_warehouse):
        """Tests that consents value is None when there are no user consents"""
        expected_consents = None

        join_outcome(True, self.mcard_entry)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]

        self.assertEqual(data["consents"], expected_consents)


class TestJoinFailEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")
        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)
        cls.mcard_entry = SchemeAccountEntryFactory(scheme_account=cls.mcard, user=cls.user)

        cls.user_consents = [
            UserConsentFactory(user=cls.user, scheme_account=cls.mcard, scheme=cls.scheme, value=True),
            UserConsentFactory(user=cls.user, scheme_account=cls.mcard, scheme=cls.scheme, value=False),
        ]

    @patch("history.data_warehouse.to_data_warehouse")
    def test_failed_join(self, mock_to_warehouse):
        join_outcome(False, self.mcard_entry)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.join.failed")
        self.assertEqual(data["origin"], "merchant.callback")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["status"], self.mcard_entry.link_status)
        self.assertNotIn("consents", data)


class TestAddAndAuthSuccessEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")
        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)
        cls.mcard_entry = SchemeAccountEntryFactory(scheme_account=cls.mcard, user=cls.user)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_success_addandauth(self, mock_to_warehouse):
        add_auth_outcome(True, self.mcard_entry)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.addandauth.success")
        self.assertEqual(data["origin"], "channel")
        self.assertEqual(data["channel"], None)
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["main_answer"], self.mcard.alt_main_answer)
        self.assertEqual(data["status"], self.mcard_entry.link_status)


class TestAddAndAuthFailEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")
        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)
        cls.mcard_entry = SchemeAccountEntryFactory(scheme_account=cls.mcard, user=cls.user)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_failed_addandauth(self, mock_to_warehouse):
        add_auth_outcome(False, self.mcard_entry)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.addandauth.failed")
        self.assertEqual(data["origin"], "channel")
        self.assertEqual(data["channel"], self.user.bundle_id)
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["status"], self.mcard_entry.link_status)


class TestAuthSuccessEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")
        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)
        cls.mcard_entry = SchemeAccountEntryFactory(scheme_account=cls.mcard, user=cls.user)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_success_auth(self, mock_to_warehouse):
        auth_outcome(True, self.mcard_entry)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.auth.success")
        self.assertEqual(data["origin"], "channel")
        self.assertEqual(data["channel"], self.user.bundle_id)
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["main_answer"], self.mcard.alt_main_answer)
        self.assertEqual(data["status"], self.mcard_entry.link_status)


class TestAuthFailEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")
        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)
        cls.mcard_entry = SchemeAccountEntryFactory(scheme_account=cls.mcard, user=cls.user)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_failed_auth(self, mock_to_warehouse):
        auth_outcome(False, self.mcard_entry)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.auth.failed")
        self.assertEqual(data["origin"], "channel")
        self.assertEqual(data["channel"], self.user.bundle_id)
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["status"], self.mcard_entry.link_status)


class TestRegisterSuccessEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")
        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)

        cls.scheme_acc_entry = SchemeAccountEntryFactory(scheme_account=cls.mcard, user=cls.user)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_success_register(self, mock_to_warehouse):
        user_consents = [
            UserConsentFactory(user=self.user, scheme_account=self.mcard, scheme=self.scheme, value=True),
            UserConsentFactory(user=self.user, scheme_account=self.mcard, scheme=self.scheme, value=False),
        ]
        expected_consents = [
            {
                "slug": consent.slug,
                "response": consent.value,
            }
            for consent in user_consents
        ]
        register_outcome(True, self.scheme_acc_entry)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.register.success")
        self.assertEqual(data["origin"], "merchant.callback")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["status"], self.scheme_acc_entry.link_status)
        self.assertEqual(data["consents"], expected_consents)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_no_consents(self, mock_to_warehouse):
        """Tests that consents value is None when there are no user consents"""
        expected_consents = None

        join_outcome(True, self.scheme_acc_entry)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]

        self.assertEqual(data["consents"], expected_consents)


class TestRegisterFailEventHandlers(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")
        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)
        cls.mcard_entry = SchemeAccountEntryFactory(scheme_account=cls.mcard, user=cls.user)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_failed_register(self, mock_to_warehouse):
        register_outcome(False, self.mcard_entry)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.register.failed")
        self.assertEqual(data["origin"], "merchant.callback")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["status"], self.mcard_entry.link_status)
        self.assertNotIn("consents", data)


class TestHistoryEvents(TestCase):
    def setUp(self) -> None:
        self.external_id = "ext_test@setup.user"
        self.email = "test@setuo.user"
        self.organisation = OrganisationFactory()
        self.organisation_2 = OrganisationFactory(name="another organisation")
        self.client_app = ClientApplicationFactory(organisation=self.organisation)
        self.bundle_id = fake.text(max_nb_chars=30)
        self.bundle = ClientApplicationBundleFactory(bundle_id=self.bundle_id, client=self.client_app)
        self.user = UserFactory(external_id=self.external_id, client=self.client_app, email=self.email)
        self.history_kwargs = {
            "user_info": user_info(user_id=self.user.id, channel=self.bundle_id),
        }
        set_history_kwargs(self.history_kwargs)
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        clean_history_kwargs(self.history_kwargs)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("history.data_warehouse.to_data_warehouse")
    def test_history_paymentcard_added_event(self, mock_to_warehouse):
        payment_card_account_entry = PaymentCardAccountEntryFactory(user=self.user)
        payment_card_account = payment_card_account_entry.payment_card_account
        self.assertTrue(mock_to_warehouse.called)
        args = mock_to_warehouse.call_args[0][0]
        self.assertTrue(args.get("event_date_time", False))
        del args["event_date_time"]
        expected = {
            "event_type": "payment.account.added",
            "origin": "channel",
            "external_user_ref": self.user.external_id,
            "internal_user_ref": self.user.id,
            "email": self.email,
            "channel": self.bundle_id,
            "payment_account_id": payment_card_account.id,
            "fingerprint": payment_card_account.fingerprint,
            "expiry_date": f"{payment_card_account.expiry_month}/{payment_card_account.expiry_year}",
            "token": payment_card_account.token,
            "status": 1,
        }
        self.assertDictEqual(expected, args)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("history.data_warehouse.to_data_warehouse")
    def test_history_paymentcard_delete_event(self, mock_to_warehouse):
        payment_card_account_entry = PaymentCardAccountEntryFactory(user=self.user)
        payment_card_account = payment_card_account_entry.payment_card_account
        pca_id = payment_card_account.id
        pca_fingerprint = payment_card_account.fingerprint
        pca_expiry = f"{int(payment_card_account.expiry_month):02d}/{int(payment_card_account.expiry_year):02d}"
        pca_token = payment_card_account.token
        pca_status = payment_card_account.status
        payment_card_account.delete()
        self.assertTrue(mock_to_warehouse.called)
        args = mock_to_warehouse.call_args[0][0]
        self.assertTrue(args.get("event_date_time", False))
        del args["event_date_time"]
        expected = {
            "event_type": "payment.account.removed",
            "origin": "channel",
            "external_user_ref": self.user.external_id,
            "internal_user_ref": self.user.id,
            "email": self.email,
            "channel": self.bundle_id,
            "payment_account_id": pca_id,
            "fingerprint": pca_fingerprint,
            "expiry_date": pca_expiry,
            "token": pca_token,
            "status": pca_status,
        }
        self.assertDictEqual(expected, args)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("history.data_warehouse.to_data_warehouse")
    def test_history_schemeaccountentry_event(self, mock_to_warehouse):
        sae = SchemeAccountEntryFactory(user=self.user, link_status=AccountLinkStatus.PENDING.value)
        sae.set_link_status(AccountLinkStatus.ACTIVE)
        self.assertTrue(mock_to_warehouse.called)
        args = mock_to_warehouse.call_args[0][0]
        self.assertTrue(args.get("event_date_time", False))
        del args["event_date_time"]
        self.assertDictEqual(
            args,
            {
                "event_type": "lc.statuschange",
                "origin": "channel",
                "external_user_ref": self.user.external_id,
                "internal_user_ref": self.user.id,
                "email": self.user.email,
                "scheme_account_id": sae.scheme_account.id,
                "loyalty_plan": sae.scheme_account.scheme.id,
                "main_answer": get_main_answer(sae.scheme_account),
                "to_status": AccountLinkStatus.ACTIVE.value,
                "channel": self.bundle_id,
            },
        )

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("history.data_warehouse.to_data_warehouse")
    def test_history_2_users_same_client_create_event(self, mock_to_warehouse):
        external_id = "ext_test@new.user"
        email = "test@new.user"
        user = UserFactory(external_id=external_id, client=self.client_app, email=email)
        self.assertTrue(mock_to_warehouse.called)
        args = mock_to_warehouse.call_args[0][0]
        self.assertTrue(args.get("event_date_time", False))
        del args["event_date_time"]
        self.assertDictEqual(
            args,
            {
                "event_type": "user.created",
                "origin": "channel",
                "channel": self.bundle_id,
                "external_user_ref": external_id,
                "email": email,
                "internal_user_ref": user.id,
            },
        )
        user2 = UserFactory(external_id="ext_user2", client=self.client_app, email="email2@test.com")
        args = mock_to_warehouse.call_args[0][0]
        self.assertTrue(args.get("event_date_time", False))
        del args["event_date_time"]
        self.assertDictEqual(
            args,
            {
                "event_type": "user.created",
                "origin": "channel",
                "channel": self.bundle_id,
                "external_user_ref": user2.external_id,
                "email": user2.email,
                "internal_user_ref": user2.id,
            },
        )

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("history.data_warehouse.to_data_warehouse")
    def test_history_1_user_in_2_bundles_create_event(self, mock_to_warehouse):
        external_id = "ext_test@new.user"
        email = "test@new.user"
        client_app = ClientApplicationFactory(organisation=self.organisation_2, name="two channels")
        bundle_id_1 = "two_channels_branch_1"
        bundle_id_2 = "two_channels_branch_2"

        ClientApplicationBundleFactory(bundle_id=bundle_id_1, client=client_app)
        ClientApplicationBundleFactory(bundle_id=bundle_id_2, client=client_app)
        # Now test by creating a user to both channels
        user = UserFactory(external_id=external_id, client=client_app, email=email)
        self.assertTrue(mock_to_warehouse.called)
        self.assertEqual(mock_to_warehouse.call_count, 2)
        channels = [bundle_id_1, bundle_id_2]
        for index in range(0, 1):
            args = mock_to_warehouse.call_args[index][0]

            self.assertTrue(args.get("event_date_time", False))
            del args["event_date_time"]

            self.assertTrue(args.get("channel") in channels)
            channels.remove(args["channel"])
            del args["channel"]

            self.assertDictEqual(
                args,
                {
                    "event_type": "user.created",
                    "origin": "channel",
                    "external_user_ref": external_id,
                    "email": email,
                    "internal_user_ref": user.id,
                },
            )

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("history.data_warehouse.to_data_warehouse")
    def test_history_user_delete_event(self, mock_to_warehouse):
        user_id = self.user.id
        self.user.delete()
        self.assertTrue(mock_to_warehouse.called)
        args = mock_to_warehouse.call_args[0][0]
        self.assertTrue(args.get("event_date_time", False))
        del args["event_date_time"]
        self.assertDictEqual(
            args,
            {
                "event_type": "user.deleted",
                "origin": "channel",
                "channel": self.bundle_id,
                "external_user_ref": self.external_id,
                "email": self.email,
                "internal_user_ref": user_id,
            },
        )


class TestUserPllAssociationEvent(TestCase):
    @classmethod
    def setUpTestData(cls):
        (
            cls.client_app,
            cls.bundle,
            cls.issuer,
            cls.payment_card,
            cls.version_header,
            cls.payload_1,
        ) = set_up_payment_card(name_on_card="Card 1")

        external_id1 = "test1@user.com"
        cls.user_wallet_1 = UserFactory(external_id=external_id1, client=cls.client_app, email=external_id1)
        external_id2 = "test2@user.com"
        cls.user_wallet_2 = UserFactory(external_id=external_id2, client=cls.client_app, email=external_id2)

        cls.scheme1, cls.scheme_bundle_association1 = set_up_scheme(cls.bundle)
        cls.scheme2, cls.scheme_bundle_association1 = set_up_scheme(cls.bundle)
        cls.payment_card_account_1 = set_up_payment_card_account(
            cls.payment_card, issuer=cls.issuer, payload=cls.payload_1
        )
        cls.payload_2 = deepcopy(cls.payload_1)
        cls.payload_2["card"]["token"] = "ABCdKWKPOPhepzxS4MfUuvTDHxr"
        cls.payload_2["card"]["name_on_card"] = "Card 2"
        cls.payload_2["card"]["fingerprint"] = "abce350d5135ab64a8f3c1097fadefd9effb"
        cls.payload_2["card"]["last_four_digits"] = 9876
        cls.payment_card_account_2 = set_up_payment_card_account(
            cls.payment_card, issuer=cls.issuer, payload=cls.payload_2
        )

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("history.data_warehouse.to_data_warehouse")
    @patch("ubiquity.models.PaymentCardSchemeEntry.vop_activate_check")
    def test_user_pll_event_call(self, mock_vop_check, mock_to_warehouse):
        scheme_account, scheme_account_entry = set_up_membership_card(self.user_wallet_1, self.scheme1)
        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_1)
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, [self.payment_card_account_1], self.user_wallet_1
        )

        args = mock_to_warehouse.call_args[0][0]

        self.assertTrue(mock_to_warehouse.called)
        self.assertEqual(args.get("event_type"), "pll_link.statuschange")
        self.assertEqual(args.get("from_state"), None)
        self.assertEqual(args.get("to_state"), WalletPLLStatus.ACTIVE)
        self.assertEqual(args.get("slug"), "")

        # test event after status has changed
        scheme_account_entry.set_link_status(AccountLinkStatus.INVALID_CREDENTIALS)
        args = mock_to_warehouse.mock_calls[1][1][0]

        self.assertEqual(args.get("event_type"), "pll_link.statuschange")
        self.assertEqual(args.get("from_state"), WalletPLLStatus.ACTIVE)
        self.assertEqual(args.get("to_state"), WalletPLLStatus.INACTIVE)
        self.assertEqual(args.get("slug"), WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)

        # test event gets call when slug changes
        self.payment_card_account_1.status = PaymentCardAccount.INVALID_CARD_DETAILS
        self.payment_card_account_1.save(update_fields=["status"])

        args = mock_to_warehouse.mock_calls[3][1][0]

        self.assertEqual(args.get("event_type"), "pll_link.statuschange")
        self.assertEqual(args.get("from_state"), WalletPLLStatus.INACTIVE)
        self.assertEqual(args.get("to_state"), WalletPLLStatus.INACTIVE)
        self.assertEqual(args.get("slug"), WalletPLLSlug.PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE.value)


class TestCreateTrustedEvent(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organisation = OrganisationFactory(name="event_test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=cls.organisation,
            name="event test client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VAbcdef",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)

        cls.user = UserFactory(external_id="test@delete.user", client=cls.client_app, email="test@delete.user")

        cls.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)

        cls.mcard = SchemeAccountFactory(scheme=cls.scheme)
        cls.pcard = PaymentCardAccountEntryFactory(user=cls.user)

    @patch("history.data_warehouse.to_data_warehouse")
    def test_create_trusted_event(self, mock_to_warehouse):
        create_trusted_event(
            self.user,
            self.mcard,
            "test.auth.fake",
            self.pcard.id,
        )

        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "tc.user.created")
        self.assertEqual(data["origin"], "channel")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["payment_account_id"], self.pcard.id)

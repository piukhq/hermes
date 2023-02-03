from unittest.mock import patch
from django.test import override_settings

from django.test import TransactionTestCase

from history.data_warehouse import (
    add_auth_outcome,
    addauth_request_lc_event,
    auth_outcome,
    auth_request_lc_event,
    join_outcome,
    join_request_lc_event,
    register_lc_event,
    register_outcome,
    remove_loyalty_card_event,
)
from scheme.models import SchemeBundleAssociation
from scheme.tests.factories import SchemeAccountFactory, SchemeBundleAssociationFactory, SchemeFactory, fake
from ubiquity.tests.factories import SchemeAccountEntryFactory, PaymentCardAccountEntryFactory
from user.tests.factories import (
    ClientApplicationBundleFactory,
    ClientApplicationFactory,
    OrganisationFactory,
    UserFactory,
)


class TestRemoveLCEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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

        super().setUpClass()

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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestRegisterLCEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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
        super().setUpClass()

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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestJoinRequestLCEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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
        super().setUpClass()

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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestAAALCEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_addauth_request_lc_event(self, mock_to_warehouse):
        addauth_request_lc_event(self.user, self.mcard, "test.auth.fake")

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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestAuthRequestEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_auth_request_lc_event(self, mock_to_warehouse):
        auth_request_lc_event(self.user, self.mcard, "test.auth.fake")

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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestJoinSuccessEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_success_join(self, mock_to_warehouse):
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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestJoinFailEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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
        super().setUpClass()

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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestAddAndAuthSuccessEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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
        super().setUpClass()

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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestAddAndAuthFailEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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
        super().setUpClass()

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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestAuthSuccessEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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
        super().setUpClass()

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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestAuthFailEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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
        super().setUpClass()

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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestRegisterSuccessEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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

        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_failed_register(self, mock_to_warehouse):
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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestRegisterFailEventHandlers(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
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
        super().setUpClass()

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

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()


class TestHistoryEvents(TransactionTestCase):

    @classmethod
    def setUpClass(cls):
        cls.external_id = "ext_test@setup.user"
        cls.email = "test@setuo.user"
        super().setUpClass()

    def setUp(self) -> None:
        self.organisation = OrganisationFactory()
        self.client_app = ClientApplicationFactory(organisation=self.organisation)
        self.bundle_id = fake.text(max_nb_chars=30)
        self.bundle = ClientApplicationBundleFactory(bundle_id=self.bundle_id, client=self.client_app)
        self.user = UserFactory(external_id=self.external_id, client=self.client_app, email=self.email)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("history.data_warehouse.to_data_warehouse")
    def test_history_paymentcard_added_event(self, mock_to_warehouse):
        payment_card_account_entry = PaymentCardAccountEntryFactory(user=self.user)
        payment_card_account = payment_card_account_entry.payment_card_account
        self.assertTrue(mock_to_warehouse.called)
        args = mock_to_warehouse.call_args[0][0]
        self.assertTrue(args.get('event_date_time', False))
        del (args['event_date_time'])
        expected = {
            'event_type': 'payment.account.added',
            'origin': 'merchant.callback',
            'external_user_ref': 'ext_test@setup.user',
            'internal_user_ref': 1,
            'email': self.email,
            'channel': self.bundle_id,
            'payment_account_id': payment_card_account.id,
            'fingerprint': payment_card_account.fingerprint,
            'expiry_date': f"{payment_card_account.expiry_month}/{payment_card_account.expiry_year}",
            'token': payment_card_account.token,
            'status': 1
        }
        self.assertDictEqual(expected, args)

    """
    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("history.data_warehouse.to_data_warehouse")
    def test_history_schemeaccountentry_event(self, mock_to_warehouse):
        SchemeAccountEntryFactory(user=self.user)
        self.assertTrue(mock_to_warehouse.called)
    """

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("history.data_warehouse.to_data_warehouse")
    def test_history_user_create_event(self, mock_to_warehouse):
        external_id = "ext_test@new.user"
        email = "test@new.user"
        user = UserFactory(external_id=external_id, client=self.client_app, email=email)
        self.assertTrue(mock_to_warehouse.called)
        args = mock_to_warehouse.call_args[0][0]
        self.assertTrue(args.get('event_date_time', False))
        del(args['event_date_time'])
        self.assertDictEqual(args, {
            "event_type": "user.created",
            "origin": "merchant.callback",
            "channel": self.bundle_id,
            "external_user_ref": external_id,
            "email": email,
            "internal_user_ref": user.id
        })

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("history.data_warehouse.to_data_warehouse")
    def test_history_user_delete_event(self, mock_to_warehouse):
        user_id = self.user.id
        self.user.delete()
        self.assertTrue(mock_to_warehouse.called)
        args = mock_to_warehouse.call_args[0][0]
        self.assertTrue(args.get('event_date_time', False))
        del (args['event_date_time'])
        self.assertDictEqual(args, {
            "event_type": "user.deleted",
            "origin": "merchant.callback",
            "channel": self.bundle_id,
            "external_user_ref": self.external_id,
            "email": self.email,
            "internal_user_ref": user_id
        })


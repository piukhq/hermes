from unittest.mock import patch

from django.test import TransactionTestCase

from history.data_warehouse import (
    add_and_auth_lc_event,
    add_auth_outcome,
    auth_outcome,
    auth_request_lc_event,
    join_outcome,
    join_request_lc_event,
    register_lc_event,
    register_outcome,
    remove_loyalty_card_event,
)
from scheme.models import SchemeBundleAssociation
from scheme.tests.factories import SchemeAccountFactory, SchemeBundleAssociationFactory, SchemeFactory
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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_remove_loyalty_card_event(self, mock_to_warehouse):
        remove_loyalty_card_event(self.user, self.mcard)

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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_register_lc_event(self, mock_to_warehouse):
        register_lc_event(self.user, self.mcard, "test.auth.fake")

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
        self.assertEqual(data["main_answer"], self.mcard.main_answer)

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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_join_request_lc_event(self, mock_to_warehouse):
        join_request_lc_event(self.user, self.mcard, "test.auth.fake")

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
    def test_add_and_auth_lc_event(self, mock_to_warehouse):
        add_and_auth_lc_event(self.user, self.mcard, "test.auth.fake")

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
        self.assertEqual(data["main_answer"], self.mcard.main_answer)

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
        self.assertEqual(data["main_answer"], self.mcard.main_answer)

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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_success_join(self, mock_to_warehouse):
        join_outcome(True, self.user, self.mcard)
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
        self.assertEqual(data["main_answer"], self.mcard.main_answer)
        self.assertEqual(data["status"], self.mcard.status)

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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_failed_join(self, mock_to_warehouse):
        join_outcome(False, self.user, self.mcard)
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
        self.assertEqual(data["status"], self.mcard.status)

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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_success_addandauth(self, mock_to_warehouse):
        add_auth_outcome(True, self.user, self.mcard)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.addandauth.success")
        self.assertEqual(data["origin"], "merchant.callback")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["main_answer"], self.mcard.main_answer)
        self.assertEqual(data["status"], self.mcard.status)

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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_failed_addandauth(self, mock_to_warehouse):
        add_auth_outcome(False, self.user, self.mcard)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.addandauth.failed")
        self.assertEqual(data["origin"], "merchant.callback")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["status"], self.mcard.status)

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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_success_auth(self, mock_to_warehouse):
        auth_outcome(True, self.user, self.mcard)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.auth.success")
        self.assertEqual(data["origin"], "merchant.callback")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["main_answer"], self.mcard.main_answer)
        self.assertEqual(data["status"], self.mcard.status)

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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_failed_auth(self, mock_to_warehouse):
        auth_outcome(False, self.user, self.mcard)
        self.assertTrue(mock_to_warehouse.called)
        data = mock_to_warehouse.call_args.args[0]
        self.assertEqual(data["event_type"], "lc.auth.failed")
        self.assertEqual(data["origin"], "merchant.callback")
        self.assertEqual(data["channel"], "test.auth.fake")
        self.assertEqual(data["external_user_ref"], self.user.external_id)
        self.assertEqual(data["internal_user_ref"], self.user.id)
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["scheme_account_id"], self.mcard.id)
        self.assertEqual(data["loyalty_plan"], self.mcard.scheme_id)
        self.assertEqual(data["status"], self.mcard.status)

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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_failed_register(self, mock_to_warehouse):
        register_outcome(True, self.user, self.mcard)
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
        self.assertEqual(data["status"], self.mcard.status)

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
        super().setUpClass()

    @patch("history.data_warehouse.to_data_warehouse")
    def test_failed_register(self, mock_to_warehouse):
        register_outcome(False, self.user, self.mcard)
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
        self.assertEqual(data["status"], self.mcard.status)

    @classmethod
    def tearDownClass(cls):
        cls.mcard.delete()
        cls.scheme.delete()
        cls.user.delete()
        cls.bundle.delete()
        cls.client_app.delete()
        cls.organisation.delete()
        super().tearDownClass()

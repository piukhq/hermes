from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework import serializers

from hermes.channels import Permit
from history.utils import GlobalMockAPITestCase
from payment_card.tests.factories import PaymentCardAccountFactory
from scheme.credentials import CARD_NUMBER, EMAIL, PASSWORD, POSTCODE
from scheme.models import SchemeAccount, SchemeBundleAssociation, SchemeCredentialQuestion
from scheme.serializers import JoinSerializer
from scheme.tests.factories import SchemeAccountFactory, SchemeCredentialAnswerFactory, SchemeCredentialQuestionFactory
from ubiquity.models import PaymentCardSchemeEntry, SchemeAccountEntry, AccountLinkStatus
from ubiquity.tasks import (
    async_all_balance,
    async_balance,
    async_link,
    async_registration,
    deleted_membership_card_cleanup,
    deleted_payment_card_cleanup,
    deleted_service_cleanup,
)
from ubiquity.tests.factories import (
    PaymentCardAccountEntryFactory,
    PaymentCardSchemeEntryFactory,
    SchemeAccountEntryFactory,
    ServiceConsentFactory,
)
from user.tests.factories import (
    ClientApplicationBundleFactory,
    ClientApplicationFactory,
    OrganisationFactory,
    UserFactory,
)


class TestTasks(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        external_id = "tasks@testbink.com"
        cls.org = OrganisationFactory(name="Barclays")
        cls.client = ClientApplicationFactory(organisation=cls.org, name="Barclays-client")
        cls.bundle = ClientApplicationBundleFactory(client=cls.client)
        cls.user = UserFactory(external_id=external_id, email=external_id)
        cls.entry = SchemeAccountEntryFactory(user=cls.user)
        cls.entry2 = SchemeAccountEntryFactory(user=cls.user)

        cls.link_entry = SchemeAccountEntryFactory(user=cls.user)
        cls.link_scheme = cls.link_entry.scheme_account.scheme
        cls.manual_question = SchemeCredentialQuestionFactory(
            scheme=cls.link_scheme,
            type=EMAIL,
            manual_question=True,
        )
        cls.auth_question_1 = SchemeCredentialQuestionFactory(
            scheme=cls.link_scheme,
            type=PASSWORD,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            auth_field=True,
        )
        cls.auth_question_2 = SchemeCredentialQuestionFactory(
            scheme=cls.link_scheme,
            type=POSTCODE,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            auth_field=True,
        )

    @patch("requests.get")
    def test_async_balance(self, mock_midas_balance):
        mock_midas_balance.return_value.status_code = AccountLinkStatus.TRIPPED_CAPTCHA
        scheme_account_id = self.entry.scheme_account.id
        scheme_slug = self.entry.scheme_account.scheme.slug
        async_balance(self.entry)

        self.assertTrue(mock_midas_balance.called)
        self.assertTrue(scheme_slug in mock_midas_balance.call_args[0][0])
        self.assertTrue(scheme_account_id in mock_midas_balance.call_args[1]["params"].values())

    @patch("ubiquity.tasks.async_balance.delay")
    def test_async_all_balance(self, mock_async_balance):
        user_id = self.user.id
        SchemeBundleAssociation.objects.create(bundle=self.bundle, scheme=self.entry.scheme_account.scheme)
        SchemeBundleAssociation.objects.create(bundle=self.bundle, scheme=self.entry2.scheme_account.scheme)
        channels_permit = Permit(self.bundle.bundle_id, client=self.bundle.client)

        async_all_balance(user_id, channels_permit=channels_permit)

        scheme_account = SchemeAccountFactory(is_deleted=True)
        deleted_entry = SchemeAccountEntryFactory(user=self.user, scheme_account=scheme_account)

        self.assertTrue(mock_async_balance.called)
        async_balance_call_args = [call_args[0][0] for call_args in mock_async_balance.call_args_list]
        self.assertTrue(self.entry in async_balance_call_args)
        self.assertTrue(self.entry2 in async_balance_call_args)
        self.assertFalse(deleted_entry in async_balance_call_args)

    @patch("ubiquity.tasks.async_balance.delay")
    def test_async_all_balance_filtering(self, mock_async_balance):
        scheme_account_1 = SchemeAccountFactory()
        scheme_account_2 = SchemeAccountFactory(scheme=scheme_account_1.scheme)
        scheme_account_3 = SchemeAccountFactory(scheme=scheme_account_1.scheme)
        scheme_account_4 = SchemeAccountFactory(scheme=scheme_account_1.scheme)

        entry_active = SchemeAccountEntryFactory(user=self.user, scheme_account=scheme_account_1)
        user = entry_active.user
        SchemeBundleAssociation.objects.create(bundle=self.bundle, scheme=scheme_account_1.scheme)
        channels_permit = Permit(self.bundle.bundle_id, client=self.bundle.client)

        entry_pending = SchemeAccountEntryFactory(
            user=user, scheme_account=scheme_account_2, link_status=AccountLinkStatus.PENDING
        )
        entry_invalid_credentials = SchemeAccountEntryFactory(
            user=user, scheme_account=scheme_account_3, link_status=AccountLinkStatus.INVALID_CREDENTIALS
        )
        entry_end_site_down = SchemeAccountEntryFactory(
            user=user, scheme_account=scheme_account_4, link_status=AccountLinkStatus.END_SITE_DOWN
        )

        async_all_balance(user.id, channels_permit=channels_permit)

        refreshed_scheme_accounts = [x[0][0] for x in mock_async_balance.call_args_list]
        self.assertIn(entry_active, refreshed_scheme_accounts)
        self.assertIn(entry_end_site_down, refreshed_scheme_accounts)
        self.assertNotIn(entry_invalid_credentials, refreshed_scheme_accounts)
        self.assertNotIn(entry_pending, refreshed_scheme_accounts)

    @patch("ubiquity.tasks.async_balance.delay")
    def test_async_all_balance_with_allowed_schemes(self, mock_async_balance):
        user_id = self.user.id
        SchemeBundleAssociation.objects.create(bundle=self.bundle, scheme=self.entry2.scheme_account.scheme)
        channels_permit = Permit(self.bundle.bundle_id, client=self.bundle.client)
        async_all_balance(user_id, channels_permit=channels_permit)
        self.assertTrue(mock_async_balance.called)
        async_balance_call_args = [call_args[0][0] for call_args in mock_async_balance.call_args_list]
        self.assertFalse(self.entry in async_balance_call_args)
        self.assertTrue(self.entry2 in async_balance_call_args)

    @patch("requests.get")
    def test_async_link_validation_error(self, mock_midas_balance):
        scheme_account = self.link_entry.scheme_account
        user_id = self.link_entry.user_id
        SchemeCredentialAnswerFactory(question=self.manual_question, scheme_account_entry=self.link_entry)

        auth_fields = {"password": "test123"}
        self.assertEqual(self.link_entry.link_status, AccountLinkStatus.ACTIVE)
        with self.assertRaises(serializers.ValidationError):
            async_link(auth_fields, scheme_account.id, user_id, False)

        self.link_entry.refresh_from_db()
        self.assertEqual(self.link_entry.link_status, AccountLinkStatus.INVALID_CREDENTIALS)
        self.assertFalse(mock_midas_balance.called)

    @patch("scheme.mixins.SchemeAccountJoinMixin.post_midas_join")
    @patch("scheme.mixins.SchemeAccountJoinMixin.save_consents")
    def test_async_register_validation_failure(self, mock_save_consents, *_):
        mock_save_consents.side_effect = ValidationError("invalid consents")
        card_number = SchemeCredentialQuestionFactory(
            scheme=self.link_scheme,
            type=CARD_NUMBER,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            manual_question=True,
        )

        SchemeCredentialAnswerFactory(
            question=card_number,
            answer="1234567",
            scheme_account_entry=self.link_entry,
        )

        scheme_account_id = self.link_entry.scheme_account.id
        user_id = self.link_entry.user_id

        async_registration(user_id, JoinSerializer, scheme_account_id, {"credentials": {}}, self.bundle.bundle_id)

        self.link_entry.scheme_account.refresh_from_db()
        self.assertEqual(self.link_entry.link_status, AccountLinkStatus.REGISTRATION_FAILED)

    @patch("ubiquity.tasks.send_merchant_metrics_for_link_delete.delay")
    def test_deleted_membership_card_cleanup_ubiquity_collision(self, mock_metrics):
        external_id_1 = "testuser@testbink.com"
        user1 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user2 = UserFactory(external_id=external_id_2, email=external_id_2)

        main_mcard = SchemeAccountFactory()
        main_mcard_entry = SchemeAccountEntryFactory(scheme_account=main_mcard, user=user1)

        # Add an Active payment account and link mcard to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)

        PaymentCardSchemeEntryFactory(payment_card_account=payment_card, scheme_account=main_mcard)

        # Add second scheme account of the same scheme to user2 and link to shared payment account.
        # This is a ubiquity collision
        mcard2 = SchemeAccountFactory(scheme=main_mcard.scheme)
        SchemeAccountEntryFactory(scheme_account=mcard2, user=user2)
        PaymentCardSchemeEntryFactory(
            payment_card_account=payment_card,
            scheme_account=mcard2,
            active_link=False,
            slug=PaymentCardSchemeEntry.UBIQUITY_COLLISION,
        )

        # TEST
        deleted_membership_card_cleanup(main_mcard_entry, "")

        main_mcard.refresh_from_db()
        self.assertTrue(main_mcard.is_deleted)

        # PLL links deleted for mcards held by user1 and
        # resolved to Active from UBIQUITY_COLLISION for mcard held by user2
        pll_links = payment_card.paymentcardschemeentry_set.all()
        self.assertEqual(len(pll_links), 1)
        self.assertTrue(pll_links[0].active_link)
        self.assertEqual(pll_links[0].slug, "")
        self.assertEqual(pll_links[0].description, "")

    @patch("ubiquity.tasks.remove_loyalty_card_event")
    @patch("ubiquity.tasks.send_merchant_metrics_for_link_delete.delay")
    def test_deleted_membership_card_cleanup_other_entries(self, mock_metrics, mock_to_warehouse):
        """
        Tests that auth credentials are deleted only for this user, and that scheme_account is not deleted when user is
        not last man standing.
        """
        external_id_1 = "testuser@testbink.com"
        user2 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user3 = UserFactory(external_id=external_id_2, email=external_id_2)

        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account, user=user2, auth_provided=False)
        scheme_account_entry_alt = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=user3, auth_provided=False
        )

        SchemeCredentialAnswerFactory(question=self.manual_question, scheme_account_entry=scheme_account_entry)
        SchemeCredentialAnswerFactory(question=self.auth_question_1, scheme_account_entry=scheme_account_entry)
        SchemeCredentialAnswerFactory(question=self.auth_question_2, scheme_account_entry=scheme_account_entry)

        SchemeCredentialAnswerFactory(question=self.manual_question, scheme_account_entry=scheme_account_entry_alt)
        SchemeCredentialAnswerFactory(question=self.auth_question_1, scheme_account_entry=scheme_account_entry_alt)
        SchemeCredentialAnswerFactory(question=self.auth_question_2, scheme_account_entry=scheme_account_entry_alt)

        answers = scheme_account_entry.schemeaccountcredentialanswer_set
        self.assertEqual(3, answers.count())
        answers = scheme_account_entry_alt.schemeaccountcredentialanswer_set
        self.assertEqual(3, answers.count())

        deleted_membership_card_cleanup(scheme_account_entry, "")

        scheme_account.refresh_from_db()

        answers = scheme_account_entry_alt.schemeaccountcredentialanswer_set
        self.assertEqual(3, answers.count())

        self.assertFalse(scheme_account.is_deleted)

        self.assertTrue(mock_to_warehouse.called)
        self.assertEqual(mock_to_warehouse.call_count, 1)

        with self.assertRaises(SchemeAccountEntry.DoesNotExist):
            SchemeAccountEntry.objects.get(scheme_account=scheme_account, user=user2)

    @patch("ubiquity.tasks.send_merchant_metrics_for_link_delete.delay")
    def test_deleted_payment_card_cleanup_ubiquity_collision(self, mock_metrics):
        external_id_1 = "testuser@testbink.com"
        user1 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user2 = UserFactory(external_id=external_id_2, email=external_id_2)

        # Add an Active payment account and link mcard to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        # This link is not created for the test because it is deleted in the api before the cleanup task
        # PaymentCardAccountEntryFactory(user=user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)

        # Add scheme account of the same scheme to both users and link to shared payment account.
        # First link will be active and the second will be a ubiquity collision
        mcard1 = SchemeAccountFactory()
        mcard2 = SchemeAccountFactory(scheme=mcard1.scheme)

        SchemeAccountEntryFactory(scheme_account=mcard1, user=user1)
        SchemeAccountEntryFactory(scheme_account=mcard2, user=user2)

        PaymentCardSchemeEntryFactory(payment_card_account=payment_card, scheme_account=mcard1, active_link=True)

        PaymentCardSchemeEntryFactory(
            payment_card_account=payment_card,
            scheme_account=mcard2,
            active_link=False,
            slug=PaymentCardSchemeEntry.UBIQUITY_COLLISION,
        )

        # TEST
        deleted_payment_card_cleanup(payment_card.id, None)

        # PLL links deleted for mcards held by user1 and
        # resolved to Active from UBIQUITY_COLLISION for mcard held by user2
        pll_links = payment_card.paymentcardschemeentry_set.all()
        self.assertEqual(len(pll_links), 1)
        self.assertTrue(pll_links[0].active_link)
        self.assertEqual(pll_links[0].slug, "")
        self.assertEqual(pll_links[0].description, "")

    @patch("payment_card.metis.delete_payment_card")
    @patch("ubiquity.tasks._send_data_to_atlas")
    def test_deleted_service_cleanup(self, mock_atlas_request, mock_delete_payment_card):
        # This task is used for API 1.x and 2.x which would create service consents when
        # creating the user.
        ServiceConsentFactory(user=self.user)

        linked_mcard_entries = self.user.schemeaccountentry_set.all()
        self.assertEqual(len(linked_mcard_entries), 3)

        # Add an Active payment account and link mcards to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=self.user, payment_card_account=payment_card)

        for entry in linked_mcard_entries:
            PaymentCardSchemeEntryFactory(payment_card_account=payment_card, scheme_account=entry.scheme_account)

        # TEST
        deleted_service_cleanup(self.user.id, {})

        self.assertTrue(mock_atlas_request.called)
        self.assertTrue(mock_delete_payment_card)

        # PLL links deleted
        for entry in linked_mcard_entries:
            pll_link = entry.scheme_account.paymentcardschemeentry_set.count()
            self.assertEqual(pll_link, 0)

        # Loyalty card links deleted
        linked_mcard_entry_count = self.user.schemeaccountentry_set.count()
        self.assertEqual(linked_mcard_entry_count, 0)

        # Payment account links deleted
        linked_pcard_entry_count = self.user.paymentcardaccountentry_set.count()
        self.assertEqual(linked_pcard_entry_count, 0)

    @patch("ubiquity.tasks._send_data_to_atlas")
    def test_deleted_service_cleanup_shared_pcard_and_mcards(self, mock_atlas_request):
        # This task is used for API 1.x and 2.x which would create service consents when
        # creating the user.
        ServiceConsentFactory(user=self.user)

        linked_mcard_entries = self.user.schemeaccountentry_set.all()
        self.assertEqual(len(linked_mcard_entries), 3)

        external_id = "testdeleteservice@testbink.com"
        user2 = UserFactory(external_id=external_id, email=external_id)

        # Add an Active payment account and link mcards to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=self.user, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)

        for entry in linked_mcard_entries:
            SchemeAccountEntryFactory(scheme_account=entry.scheme_account, user=user2)
            PaymentCardSchemeEntryFactory(payment_card_account=payment_card, scheme_account=entry.scheme_account)

        # TEST
        deleted_service_cleanup(self.user.id, {})

        self.assertTrue(mock_atlas_request.called)

        # PLL links deleted
        for entry in linked_mcard_entries:
            pll_link = entry.scheme_account.paymentcardschemeentry_set.count()
            self.assertEqual(pll_link, 1)

        # Loyalty card links deleted for user 1
        linked_mcard_entry_count = self.user.schemeaccountentry_set.count()
        self.assertEqual(linked_mcard_entry_count, 0)

        linked_mcard_entry_count = user2.schemeaccountentry_set.count()
        self.assertEqual(linked_mcard_entry_count, 3)

        # Payment account links deleted for user 1
        linked_pcard_entry_count = self.user.paymentcardaccountentry_set.count()
        self.assertEqual(linked_pcard_entry_count, 0)

        linked_pcard_entry_count = user2.paymentcardaccountentry_set.count()
        self.assertEqual(linked_pcard_entry_count, 1)

    @patch("ubiquity.tasks._send_data_to_atlas")
    def test_deleted_service_cleanup_ubiquity_collision(self, mock_atlas_request):
        # This task is used for API 1.x and 2.x which would create service consents when
        # creating the user.
        ServiceConsentFactory(user=self.user)

        linked_mcard_entries = self.user.schemeaccountentry_set.all()
        self.assertEqual(len(linked_mcard_entries), 3)

        external_id = "testdeleteservice@testbink.com"
        user2 = UserFactory(external_id=external_id, email=external_id)

        # Add an Active payment account and link mcards to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=self.user, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)

        for entry in linked_mcard_entries:
            PaymentCardSchemeEntryFactory(payment_card_account=payment_card, scheme_account=entry.scheme_account)

        # Add second scheme account of the same scheme to user2 and link to shared payment account.
        # This is a ubiquity collision
        mcard2 = SchemeAccountFactory(scheme=linked_mcard_entries[0].scheme_account.scheme)
        SchemeAccountEntryFactory(scheme_account=mcard2, user=user2)
        PaymentCardSchemeEntryFactory(
            payment_card_account=payment_card,
            scheme_account=mcard2,
            active_link=False,
            slug=PaymentCardSchemeEntry.UBIQUITY_COLLISION,
        )

        # TEST
        deleted_service_cleanup(self.user.id, {})

        self.assertTrue(mock_atlas_request.called)

        # PLL links deleted for mcards held by user1 and
        # resolved to Active from UBIQUITY_COLLISION for mcard held by user2
        pll_links = payment_card.paymentcardschemeentry_set.all()
        self.assertEqual(len(pll_links), 1)
        self.assertTrue(pll_links[0].active_link)
        self.assertEqual(pll_links[0].slug, "")
        self.assertEqual(pll_links[0].description, "")

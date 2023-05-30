from unittest.mock import patch

import arrow
from django.core.exceptions import ValidationError
from rest_framework import serializers

from hermes.channels import Permit
from history.utils import GlobalMockAPITestCase
from payment_card.tests.factories import PaymentCardAccountFactory
from scheme.credentials import CARD_NUMBER, EMAIL, PASSWORD, POSTCODE
from scheme.models import SchemeBundleAssociation, SchemeCredentialQuestion
from scheme.serializers import JoinSerializer
from scheme.tests.factories import SchemeAccountFactory, SchemeCredentialAnswerFactory, SchemeCredentialQuestionFactory
from ubiquity.models import (
    AccountLinkStatus,
    PaymentCardSchemeEntry,
    PllUserAssociation,
    SchemeAccountEntry,
    WalletPLLStatus,
)
from ubiquity.tasks import (
    async_all_balance,
    async_balance,
    async_link,
    async_registration,
    deleted_membership_card_cleanup,
    deleted_payment_card_cleanup,
    deleted_service_cleanup,
)
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory, ServiceConsentFactory
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
        cls.entry = SchemeAccountEntryFactory(user=cls.user, link_status=AccountLinkStatus.ACTIVE)
        cls.entry2 = SchemeAccountEntryFactory(user=cls.user, link_status=AccountLinkStatus.ACTIVE)

        cls.link_entry = SchemeAccountEntryFactory(user=cls.user, link_status=AccountLinkStatus.ACTIVE)
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

        entry_active = SchemeAccountEntryFactory(
            user=self.user, scheme_account=scheme_account_1, link_status=AccountLinkStatus.ACTIVE
        )
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

        self.link_entry.refresh_from_db()
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

        # PaymentCardSchemeEntryFactory(payment_card_account=payment_card, scheme_account=main_mcard)
        PllUserAssociation.link_users_scheme_account_to_payment(main_mcard, payment_card, user1)

        # Add second scheme account of the same scheme to user2 and link to shared payment account.
        # This is a ubiquity collision
        mcard2 = SchemeAccountFactory(scheme=main_mcard.scheme)
        SchemeAccountEntryFactory(scheme_account=mcard2, user=user2)
        """
        PaymentCardSchemeEntryFactory(
            payment_card_account=payment_card,
            scheme_account=mcard2,
            active_link=False,
            slug=PaymentCardSchemeEntry.UBIQUITY_COLLISION,
        )
        """
        PllUserAssociation.link_users_scheme_account_to_payment(mcard2, payment_card, user2)

        # TEST
        deleted_membership_card_cleanup(main_mcard_entry, "")

        main_mcard.refresh_from_db()
        self.assertTrue(main_mcard.is_deleted)

        # PLL links deleted for mcards held by user1 and
        # resolved to Active from UBIQUITY_COLLISION for mcard held by user2
        links = payment_card.paymentcardschemeentry_set.all()
        pll_users = PllUserAssociation.objects.all()

        self.assertEqual(len(pll_users), 1)
        self.assertEqual(len(links), 1)
        self.assertEqual(pll_users[0].pll, links[0])

        self.assertTrue(links[0].active_link)
        self.assertEqual(pll_users[0].slug, "")
        self.assertEqual(pll_users[0].state, WalletPLLStatus.ACTIVE)

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
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account, user=user2)
        scheme_account_entry_alt = SchemeAccountEntryFactory(scheme_account=scheme_account, user=user3)

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

        # PaymentCardSchemeEntryFactory(payment_card_account=payment_card, scheme_account=mcard1, active_link=True)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user1)

        """
        PaymentCardSchemeEntryFactory(
            payment_card_account=payment_card,
            scheme_account=mcard2,
            active_link=False,
            slug=PaymentCardSchemeEntry.UBIQUITY_COLLISION,
        )
        """
        PllUserAssociation.link_users_scheme_account_to_payment(mcard2, payment_card, user2)

        # TEST
        deleted_payment_card_cleanup(payment_card.id, None, user1.id)

        # PLL links deleted for mcards held by user1 and
        # resolved to Active from UBIQUITY_COLLISION for mcard held by user2
        links = payment_card.paymentcardschemeentry_set.all()
        pll_users = PllUserAssociation.objects.all()

        self.assertEqual(len(pll_users), 1)
        self.assertEqual(len(links), 1)
        self.assertEqual(pll_users[0].pll, links[0])

        self.assertTrue(links[0].active_link)
        self.assertEqual(pll_users[0].slug, "")
        self.assertEqual(pll_users[0].state, WalletPLLStatus.ACTIVE)

    @patch("ubiquity.tasks.send_merchant_metrics_for_link_delete.delay")
    def test_deleted_membership_card_identical_2_wallet(self, mock_metrics):
        external_id_1 = "testuser@testbink.com"
        user1 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user2 = UserFactory(external_id=external_id_2, email=external_id_2)

        payment_card = PaymentCardAccountFactory()
        membership_card = SchemeAccountFactory()

        # add payment card and membership card to wallet 1
        SchemeAccountEntryFactory(scheme_account=membership_card, user=user1)
        PaymentCardAccountEntryFactory(user=user1, payment_card_account=payment_card)
        PllUserAssociation.link_users_scheme_account_to_payment(membership_card, payment_card, user1)

        # add same payment card and membership card accounts to wallet 2
        sae2 = SchemeAccountEntryFactory(scheme_account=membership_card, user=user2)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)
        PllUserAssociation.link_users_scheme_account_to_payment(membership_card, payment_card, user2)

        # check status of set up links
        base_links = payment_card.paymentcardschemeentry_set.all()
        pll_user_links = PllUserAssociation.objects.all()

        self.assertEqual(len(pll_user_links), 2)
        self.assertEqual(len(base_links), 1)
        self.assertEqual(pll_user_links[0].pll, base_links[0])
        self.assertEqual(pll_user_links[1].pll, base_links[0])
        self.assertEqual(pll_user_links[0].slug, "")
        # Not a ubiquity collision because same scheme and payment accounts and shared base link
        self.assertEqual(pll_user_links[0].state, WalletPLLStatus.ACTIVE)
        self.assertEqual(pll_user_links[1].slug, "")
        self.assertEqual(pll_user_links[1].state, WalletPLLStatus.ACTIVE)
        self.assertTrue(base_links[0].active_link)

        deleted_membership_card_cleanup(sae2, arrow.utcnow().format())

        base_links = payment_card.paymentcardschemeentry_set.all()
        pll_user_links = PllUserAssociation.objects.all()

        self.assertEqual(len(pll_user_links), 1)
        self.assertEqual(len(base_links), 1)
        self.assertEqual(pll_user_links[0].user, user1)

    @patch("ubiquity.tasks.send_merchant_metrics_for_link_delete.delay")
    def test_deleted_payment_card_identical_2_wallet(self, mock_metrics):
        external_id_1 = "testuser@testbink.com"
        user1 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user2 = UserFactory(external_id=external_id_2, email=external_id_2)

        payment_card = PaymentCardAccountFactory()
        membership_card = SchemeAccountFactory()

        # add payment card and membership card to wallet 1
        SchemeAccountEntryFactory(scheme_account=membership_card, user=user1)
        PaymentCardAccountEntryFactory(user=user1, payment_card_account=payment_card)
        PllUserAssociation.link_users_scheme_account_to_payment(membership_card, payment_card, user1)

        # add same payment card and membership card accounts to wallet 2
        SchemeAccountEntryFactory(scheme_account=membership_card, user=user2)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)
        PllUserAssociation.link_users_scheme_account_to_payment(membership_card, payment_card, user2)

        # check status of set up links
        base_links = payment_card.paymentcardschemeentry_set.all()
        pll_user_links = PllUserAssociation.objects.all()

        self.assertEqual(len(pll_user_links), 2)
        self.assertEqual(len(base_links), 1)
        self.assertEqual(pll_user_links[0].pll, base_links[0])
        self.assertEqual(pll_user_links[1].pll, base_links[0])
        self.assertEqual(pll_user_links[0].slug, "")
        # Not a ubiquity collision because same scheme and payment accounts and shared base link
        self.assertEqual(pll_user_links[0].state, WalletPLLStatus.ACTIVE)
        self.assertEqual(pll_user_links[1].slug, "")
        self.assertEqual(pll_user_links[1].state, WalletPLLStatus.ACTIVE)
        self.assertTrue(base_links[0].active_link)

        deleted_payment_card_cleanup(payment_card.id, None, user_id=user2.id)

        base_links = payment_card.paymentcardschemeentry_set.all()
        pll_user_links = PllUserAssociation.objects.all()

        self.assertEqual(len(pll_user_links), 1)
        self.assertEqual(len(base_links), 1)
        self.assertEqual(pll_user_links[0].user, user1)

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

        PllUserAssociation.link_users_scheme_accounts(payment_card, linked_mcard_entries)
        assert PllUserAssociation.objects.filter(user=self.user).count() == 3

        # TEST
        deleted_service_cleanup(self.user.id, {})

        self.assertTrue(mock_atlas_request.called)
        self.assertTrue(mock_delete_payment_card)

        # PLL User Associations deleted
        pll_user_assoc_count = PllUserAssociation.objects.filter(user=self.user).count()
        self.assertEqual(0, pll_user_assoc_count)

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

        PllUserAssociation.link_users_scheme_accounts(payment_card, linked_mcard_entries)
        assert PllUserAssociation.objects.filter(user=self.user).count() == 3

        for entry in linked_mcard_entries:
            mcard_entry = SchemeAccountEntryFactory(scheme_account=entry.scheme_account, user=user2)
            PllUserAssociation.link_users_scheme_account_entry_to_payment(mcard_entry, payment_card)

        # TEST
        deleted_service_cleanup(self.user.id, {})

        self.assertTrue(mock_atlas_request.called)

        # PLL User Associations deleted for user 1
        pll_user_assoc_count = PllUserAssociation.objects.filter(user=self.user).count()
        self.assertEqual(0, pll_user_assoc_count)

        pll_user_assoc_count = PllUserAssociation.objects.filter(user=user2).count()
        self.assertEqual(3, pll_user_assoc_count)

        # PLL link not deleted since user 2 still has both cards
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

        # for entry in linked_mcard_entries:
        #   PaymentCardSchemeEntryFactory(payment_card_account=payment_card, scheme_account=entry.scheme_account)

        PllUserAssociation.link_users_scheme_accounts(payment_card, linked_mcard_entries)
        # Add second scheme account of the same scheme to user2 and link to shared payment account.
        # This is a ubiquity collision
        mcard2 = SchemeAccountFactory(scheme=linked_mcard_entries[0].scheme_account.scheme)
        sae_collide = SchemeAccountEntryFactory(scheme_account=mcard2, user=user2)
        """
        PaymentCardSchemeEntryFactory(
            payment_card_account=payment_card,
            scheme_account=mcard2,
            active_link=False,
            slug=PaymentCardSchemeEntry.UBIQUITY_COLLISION,
        )
        """
        PllUserAssociation.link_users_scheme_account_entry_to_payment(sae_collide, payment_card)
        pll_users = PllUserAssociation.objects.all()
        links = PaymentCardSchemeEntry.objects.all()
        self.assertEqual(len(pll_users), 4)
        self.assertEqual(len(links), 4)
        # TEST
        deleted_service_cleanup(self.user.id, {})

        self.assertTrue(mock_atlas_request.called)

        # PLL links deleted for mcards held by user1 and
        # resolved to Active from UBIQUITY_COLLISION for mcard held by user2
        links = payment_card.paymentcardschemeentry_set.all()
        pll_users = PllUserAssociation.objects.all()

        self.assertEqual(len(pll_users), 1)
        self.assertEqual(len(links), 1)
        self.assertEqual(pll_users[0].pll, links[0])

        self.assertTrue(links[0].active_link)
        self.assertEqual(pll_users[0].slug, "")
        self.assertEqual(pll_users[0].state, WalletPLLStatus.ACTIVE)

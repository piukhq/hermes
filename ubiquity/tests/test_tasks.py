import socket
import typing
import uuid
from unittest.mock import patch

import arrow
from django.core.exceptions import ValidationError

from hermes.channels import Permit
from history.utils import GlobalMockAPITestCase
from payment_card.tests.factories import PaymentCardAccountFactory
from scheme.credentials import CARD_NUMBER, EMAIL, PASSWORD, POSTCODE, CredentialAnswers
from scheme.encryption import AESCipher
from scheme.models import JourneyTypes, SchemeBundleAssociation, SchemeCredentialQuestion
from scheme.serializers import JoinSerializer
from scheme.tests.factories import (
    SchemeAccountFactory,
    SchemeBalanceDetailsFactory,
    SchemeCredentialAnswerFactory,
    SchemeCredentialQuestionFactory,
)
from ubiquity.channel_vault import AESKeyNames
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

if typing.TYPE_CHECKING:
    from user.models import CustomUser


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

    @staticmethod
    def trusted_channel_user() -> "CustomUser":
        bundle = ClientApplicationBundleFactory(is_trusted=True)
        external_id = "trusted_channel_user"
        return UserFactory(external_id=external_id, email=external_id, client=bundle.client)

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
    def test_async_link_add_and_auth_journey_success(self, mock_midas_balance):
        # Setup db tables
        scheme_account = SchemeAccountFactory()
        card_number = SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme,
            type=CARD_NUMBER,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            manual_question=True,
        )
        SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme,
            type=POSTCODE,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            auth_field=True,
            is_stored=False,
        )
        entry_pending = SchemeAccountEntryFactory(
            user=self.user, scheme_account=scheme_account, link_status=AccountLinkStatus.ADD_AUTH_PENDING
        )
        SchemeCredentialAnswerFactory(question=card_number, answer="1234567", scheme_account_entry=entry_pending)

        user_id = entry_pending.user.id

        # Mock Midas response
        mock_midas_balance.return_value.status_code = 200
        mock_midas_balance.return_value.json.return_value = {
            "points": 21.21,
            "value": 21.21,
            "value_label": "£21.21",
            "reward_tier": 0,
            "scheme_account_id": scheme_account.id,
            "user_set": str(user_id),
            "points_label": "21",
        }

        self.assertEqual(entry_pending.link_status, AccountLinkStatus.ADD_AUTH_PENDING)

        credential_answers = CredentialAnswers()
        credential_answers.authorise = {"postcode": "SL5 5TD"}
        async_link(
            credential_answers=credential_answers,
            consents=None,
            scheme_account_id=scheme_account.id,
            user_id=user_id,
            payment_cards_to_link=[],
            headers={"X-azure-ref": "azure"},
        )
        entry_pending.refresh_from_db()

        # Check AccountLinkStatus and correct payload sent to Midas
        self.assertEqual(entry_pending.link_status, AccountLinkStatus.ACTIVE)

        expected_midas_payload = {
            "scheme_account_id": scheme_account.id,
            "credentials": '{"card_number": "1234567", "postcode": "SL5 5TD", "consents": []}',
            "user_set": str(user_id),
            "status": AccountLinkStatus.ADD_AUTH_PENDING.value,
            "journey_type": JourneyTypes.LINK.value,
            "bink_user_id": user_id,
        }

        expected_midas_headers = {
            "User-agent": f"Hermes on {socket.gethostname()}",
            "X-azure-ref": "azure",
        }

        mock_request_params = mock_midas_balance.call_args[1]
        mock_request_params["params"]["credentials"] = AESCipher(AESKeyNames.AES_KEY).decrypt(
            mock_request_params["params"]["credentials"]
        )
        self.assertEqual(
            expected_midas_payload,
            mock_request_params["params"],
        )

        # Will raise error if not valid UUID or if transaction is missing from headers
        uuid.UUID(mock_request_params["headers"].pop("transaction"))
        self.assertEqual(
            expected_midas_headers,
            mock_request_params["headers"],
        )

    @patch("requests.get")
    def test_async_link_success_multi_user_wallet(self, mock_midas_balance):
        # Setup db tables
        scheme_account = SchemeAccountFactory()
        card_number = SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme,
            type=CARD_NUMBER,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            manual_question=True,
        )
        SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme,
            type=POSTCODE,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            auth_field=True,
        )
        SchemeBalanceDetailsFactory(scheme_id=scheme_account.scheme)
        multi_wallet_card_number = "1234567"

        # Setup First SchemeAccountEntry
        entry_pending_1 = SchemeAccountEntryFactory(
            user=self.user, scheme_account=scheme_account, link_status=AccountLinkStatus.ADD_AUTH_PENDING
        )
        SchemeCredentialAnswerFactory(
            question=card_number,
            answer=multi_wallet_card_number,
            scheme_account_entry=entry_pending_1,
        )
        user_id = entry_pending_1.user.id

        # Mock first Midas response body
        mock_midas_balance.return_value.status_code = 200
        midas_resp_body = {
            "points": 21.21,
            "value": 21.21,
            "value_label": "£21.21",
            "reward_tier": 0,
            "scheme_account_id": scheme_account.id,
            "user_set": f"{user_id}",
            "points_label": "21",
        }
        mock_midas_balance.return_value.json.return_value = midas_resp_body

        self.assertEqual(entry_pending_1.link_status, AccountLinkStatus.ADD_AUTH_PENDING)

        credential_answers = CredentialAnswers()
        credential_answers.authorise = {"postcode": "SL5 5TD"}
        async_link(
            credential_answers=credential_answers,
            consents=None,
            scheme_account_id=scheme_account.id,
            user_id=user_id,
            payment_cards_to_link=[],
        )
        entry_pending_1.refresh_from_db()

        # Check first SchemeAccountEntry.link_status activated and correct JourneyType sent to Midas for first request
        self.assertEqual(entry_pending_1.link_status, AccountLinkStatus.ACTIVE)
        mock_request_params_1 = mock_midas_balance.call_args_list[0][1]
        self.assertEqual(
            mock_request_params_1["params"]["journey_type"],
            JourneyTypes.LINK,
        )

        # Setup Second SchemeAccountEntry
        external_id_2 = "tasks1@testbink.com"
        user_2 = UserFactory(external_id=external_id_2, email=external_id_2)
        entry_pending_2 = SchemeAccountEntryFactory(
            user=user_2, scheme_account=scheme_account, link_status=AccountLinkStatus.ADD_AUTH_PENDING
        )
        SchemeCredentialAnswerFactory(
            question=card_number,
            answer=multi_wallet_card_number,
            scheme_account_entry=entry_pending_2,
        )
        user_id_2 = entry_pending_2.user.id

        # Mock second Midas response body
        midas_resp_body["user_set"] = f"{user_id},{user_id_2}"
        mock_midas_balance.return_value.json.return_value = midas_resp_body

        self.assertEqual(entry_pending_2.link_status, AccountLinkStatus.ADD_AUTH_PENDING)

        async_link(
            credential_answers=credential_answers,
            consents=None,
            scheme_account_id=scheme_account.id,
            user_id=user_id_2,
            payment_cards_to_link=[],
        )
        entry_pending_2.refresh_from_db()

        # Check second SchemeAccountEntry.link_status activated and correct JourneyType sent to Midas for second request
        self.assertEqual(entry_pending_2.link_status, AccountLinkStatus.ACTIVE)
        mock_request_params_2 = mock_midas_balance.call_args_list[1][1]
        self.assertEqual(
            mock_request_params_2["params"]["journey_type"],
            JourneyTypes.LINK,
        )

    @patch("requests.get")
    def test_async_link_auth_journey_success(self, mock_midas_balance):
        """
        For AUTH request journey, we should always send LINK JourneyType to Midas.
        """
        scheme_account = SchemeAccountFactory()
        card_number = SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme,
            type=CARD_NUMBER,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            manual_question=True,
        )
        SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme,
            type=POSTCODE,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            auth_field=True,
        )
        entry_pending = SchemeAccountEntryFactory(
            user=self.user,
            scheme_account=scheme_account,
            link_status=AccountLinkStatus.AUTH_PENDING,
        )
        SchemeCredentialAnswerFactory(question=card_number, answer="1234567", scheme_account_entry=entry_pending)

        user_id = entry_pending.user.id

        # Mock Midas response
        mock_midas_balance.return_value.status_code = 200
        mock_midas_balance.return_value.json.return_value = {
            "points": 21.21,
            "value": 21.21,
            "value_label": "£21.21",
            "reward_tier": 0,
            "scheme_account_id": scheme_account.id,
            "user_set": f"{user_id}",
            "points_label": "21",
        }

        self.assertEqual(entry_pending.link_status, AccountLinkStatus.AUTH_PENDING)
        self.assertEqual(entry_pending.authorised, False)

        credential_answers = CredentialAnswers()
        credential_answers.authorise = {"postcode": "SL5 5TD"}
        async_link(
            credential_answers=credential_answers,
            consents=None,
            scheme_account_id=scheme_account.id,
            user_id=user_id,
            payment_cards_to_link=[],
            headers={"X-azure-ref": "azure"},
        )
        entry_pending.refresh_from_db()

        # Check AccountLinkStatus and correct payload sent to Midas
        self.assertEqual(entry_pending.link_status, AccountLinkStatus.ACTIVE)
        self.assertEqual(entry_pending.authorised, True)

        expected_midas_payload = {
            "scheme_account_id": scheme_account.id,
            "credentials": '{"card_number": "1234567", "postcode": "SL5 5TD", "consents": []}',
            "user_set": str(user_id),
            "status": AccountLinkStatus.AUTH_PENDING.value,
            "journey_type": JourneyTypes.LINK.value,
            "bink_user_id": user_id,
        }

        expected_midas_headers = {
            "User-agent": f"Hermes on {socket.gethostname()}",
            "X-azure-ref": "azure",
        }

        mock_request_params = mock_midas_balance.call_args[1]
        mock_request_params["params"]["credentials"] = AESCipher(AESKeyNames.AES_KEY).decrypt(
            mock_request_params["params"]["credentials"]
        )
        self.assertEqual(
            expected_midas_payload,
            mock_request_params["params"],
        )

        # Will raise error if not valid UUID or if transaction is missing from headers
        uuid.UUID(mock_request_params["headers"].pop("transaction"))
        self.assertEqual(
            expected_midas_headers,
            mock_request_params["headers"],
        )

    @patch("requests.get")
    def test_async_link_auth_journey_invalid_creds(self, mock_midas_balance):
        """
        For AUTH request journey, we should always send LINK JourneyType to Midas.
        """
        scheme_account = SchemeAccountFactory()
        card_number = SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme,
            type=CARD_NUMBER,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            manual_question=True,
        )
        SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme,
            type=POSTCODE,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            auth_field=True,
        )
        entry_pending = SchemeAccountEntryFactory(
            user=self.user,
            scheme_account=scheme_account,
            link_status=AccountLinkStatus.AUTH_PENDING,
        )
        SchemeCredentialAnswerFactory(question=card_number, answer="1234567", scheme_account_entry=entry_pending)

        user_id = entry_pending.user.id

        # Mock Midas response
        mock_midas_balance.return_value.status_code = 403

        self.assertEqual(entry_pending.link_status, AccountLinkStatus.AUTH_PENDING)
        self.assertEqual(entry_pending.authorised, False)

        credential_answers = CredentialAnswers()
        credential_answers.authorise = {"postcode": "wrong"}
        async_link(
            credential_answers=credential_answers,
            consents=None,
            scheme_account_id=scheme_account.id,
            user_id=user_id,
            payment_cards_to_link=[],
        )
        entry_pending.refresh_from_db()

        # Check AccountLinkStatus and correct JourneyType sent to Midas
        self.assertEqual(entry_pending.link_status, AccountLinkStatus.INVALID_CREDENTIALS)
        self.assertEqual(entry_pending.authorised, False)
        mock_request_params = mock_midas_balance.call_args[1]
        self.assertEqual(
            mock_request_params["params"]["journey_type"],
            JourneyTypes.LINK,
        )

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
        user1_channel = user1.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id
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

        PllUserAssociation.link_users_scheme_account_to_payment(mcard2, payment_card, user2)

        # TEST
        deleted_payment_card_cleanup(payment_card.id, None, user1.id, channel_slug=user1_channel)

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

    @patch("message_lib.producer.MessageProducer._MessageProducerQueueHandler.send_message")
    def test_loyalty_card_removed_event_sent_when_deleting_pcard_trusted_channel(self, mock_send_message):
        """
        A LoyaltyCardRemoved (trusted channel) event should be sent when the last payment card in a retailer
        (trusted) channel is unlinked from a loyalty card.

        This test is for when the unlinking happens specifically when a payment card is deleted.
        """
        trusted_user1 = self.trusted_channel_user()
        external_id_1 = "testuser@testbink.com"
        user1 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user2 = UserFactory(external_id=external_id_2, email=external_id_2)

        # Add an Active payment account and link mcard to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        # This link is not created for the test because it is deleted in the api before the cleanup task
        # PaymentCardAccountEntryFactory(user=trusted_user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)

        # Add scheme account to all users
        mcard1 = SchemeAccountFactory(card_number="1111")

        SchemeAccountEntryFactory(scheme_account=mcard1, user=trusted_user1)
        SchemeAccountEntryFactory(scheme_account=mcard1, user=user1)
        SchemeAccountEntryFactory(scheme_account=mcard1, user=user2)

        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, trusted_user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user2)

        mock_send_message.call_count = 0
        trusted_user1_channel = trusted_user1.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id
        # TEST
        deleted_payment_card_cleanup(
            payment_card.id,
            None,
            trusted_user1.id,
            trusted_user1_channel,
        )

        expected_msg_body = {}
        expected_msg_headers = {
            "X-azure-ref": None,
            "bink-user-id": str(trusted_user1.id),
            "channel": trusted_user1_channel,
            "loyalty-plan": mcard1.scheme.slug,
            "request-id": str(mcard1.id),
            # "transaction-id": "5479d204-6da8-11ee-af1c-3af9d391be47",
            "type": "loyalty_card.removed.bink",
        }

        # dw user pll status change event -> this midas loyalty card removed event
        self.assertEqual(2, mock_send_message.call_count)

        call_args = mock_send_message.call_args_list[-1]
        self.assertEqual((expected_msg_body,), call_args.args)
        # check if expected_message_headers is a subset of headers. Full headers will have a random transaction id.
        self.assertEqual(call_args.kwargs["headers"], call_args.kwargs["headers"] | expected_msg_headers)
        self.assertIn("transaction-id", call_args.kwargs["headers"])

    @patch("message_lib.producer.MessageProducer._MessageProducerQueueHandler.send_message")
    def test_loyalty_card_removed_event_sent_when_deleting_pcard_non_trusted_channel(self, mock_send_message):
        """
        A LoyaltyCardRemoved (non-trusted channel) event should be sent when the last payment card in a
        channel is unlinked from a loyalty card AND there are no other non-trusted channels that hold a link
        for the given loyalty card.

        This test is for when the unlinking happens specifically when a payment card is deleted.
        """
        trusted_user1 = self.trusted_channel_user()
        external_id_1 = "testuser@testbink.com"
        user1 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user2 = UserFactory(external_id=external_id_2, email=external_id_2)

        # Add an Active payment account and link mcard to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        # This link is not created for the test because it is deleted in the api before the cleanup task
        # PaymentCardAccountEntryFactory(user=user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=trusted_user1, payment_card_account=payment_card)
        user2_pcard_entry = PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)

        # Add scheme account to all users
        mcard1 = SchemeAccountFactory()

        SchemeAccountEntryFactory(scheme_account=mcard1, user=trusted_user1)
        SchemeAccountEntryFactory(scheme_account=mcard1, user=user1)
        SchemeAccountEntryFactory(scheme_account=mcard1, user=user2)

        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, trusted_user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user2)

        mock_send_message.call_count = 0
        user1_channel = user1.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id
        user2_channel = user2.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id

        # TEST
        deleted_payment_card_cleanup(
            payment_card.id,
            None,
            user1.id,
            user1_channel,
        )

        # a data warehouse message is sent but loyalty card removed event is not since the link
        # exists in another non-retailer wallet
        self.assertEqual(1, mock_send_message.call_count)
        mock_send_message.call_count = 0

        user2_pcard_entry.delete()
        deleted_payment_card_cleanup(
            payment_card.id,
            None,
            user2.id,
            user2_channel,
        )

        expected_msg_body = {}
        expected_msg_headers = {
            "X-azure-ref": None,
            "bink-user-id": str(user2.id),
            "channel": user2_channel,
            "loyalty-plan": mcard1.scheme.slug,
            "request-id": str(mcard1.id),
            # "transaction-id": "5479d204-6da8-11ee-af1c-3af9d391be47",
            "type": "loyalty_card.removed.bink",
        }

        # dw user pll status change event -> this midas loyalty card removed event
        self.assertEqual(2, mock_send_message.call_count)

        call_args = mock_send_message.call_args_list[-1]
        self.assertEqual((expected_msg_body,), call_args.args)
        # check if expected_message_headers is a subset of headers. Full headers will have a random transaction id.
        self.assertEqual(call_args.kwargs["headers"], call_args.kwargs["headers"] | expected_msg_headers)
        self.assertIn("transaction-id", call_args.kwargs["headers"])

    @patch("message_lib.producer.MessageProducer._MessageProducerQueueHandler.send_message")
    def test_loyalty_card_removed_event_sent_when_deleting_mcard_trusted_channel(self, mock_send_message):
        """
        A LoyaltyCardRemoved (trusted channel) event should be sent when the last payment card in a retailer
        (trusted) channel is unlinked from a loyalty card.

        This test is when the unlinking happens specifically when a loyalty card is deleted.
        """
        trusted_user1 = self.trusted_channel_user()
        external_id_1 = "testuser@testbink.com"
        user1 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user2 = UserFactory(external_id=external_id_2, email=external_id_2)

        # Add an Active payment account and link mcard to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=trusted_user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)

        # Add scheme account to all users
        mcard1 = SchemeAccountFactory(card_number="1111")

        tc_user_mcard_entry = SchemeAccountEntryFactory(scheme_account=mcard1, user=trusted_user1)
        SchemeAccountEntryFactory(scheme_account=mcard1, user=user1)
        SchemeAccountEntryFactory(scheme_account=mcard1, user=user2)

        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, trusted_user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user2)

        mock_send_message.call_count = 0
        trusted_user1_channel = trusted_user1.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id
        # TEST

        deleted_membership_card_cleanup(
            tc_user_mcard_entry,
            arrow.utcnow().format(),
            channel_slug=trusted_user1_channel,
        )

        expected_msg_body = {}
        expected_msg_headers = {
            "X-azure-ref": None,
            "bink-user-id": str(trusted_user1.id),
            "channel": trusted_user1_channel,
            "loyalty-plan": mcard1.scheme.slug,
            "request-id": str(mcard1.id),
            # "transaction-id": "5479d204-6da8-11ee-af1c-3af9d391be47",
            "type": "loyalty_card.removed.bink",
        }

        # dw user pll status change event -> dw remove loyalty card event -> this midas loyalty card removed event
        self.assertEqual(3, mock_send_message.call_count)

        call_args = mock_send_message.call_args_list[-1]
        self.assertEqual((expected_msg_body,), call_args.args)
        # check if expected_message_headers is a subset of headers. Full headers will have a random transaction id.
        self.assertEqual(call_args.kwargs["headers"], call_args.kwargs["headers"] | expected_msg_headers)
        self.assertIn("transaction-id", call_args.kwargs["headers"])

    @patch("message_lib.producer.MessageProducer._MessageProducerQueueHandler.send_message")
    def test_loyalty_card_removed_event_sent_when_deleting_mcard_non_trusted_channel(self, mock_send_message):
        """
        A LoyaltyCardRemoved (non-trusted channel) event should be sent when the last payment card in a
        channel is unlinked from a loyalty card AND there are no other non-trusted channels that hold a link
        for the given loyalty card.

        This test is for when the unlinking happens specifically when a loyalty card is deleted.
        """
        trusted_user1 = self.trusted_channel_user()
        external_id_1 = "testuser@testbink.com"
        user1 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user2 = UserFactory(external_id=external_id_2, email=external_id_2)

        # Add an Active payment account and link mcard to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=trusted_user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)

        # Add scheme account to all users
        mcard1 = SchemeAccountFactory()

        SchemeAccountEntryFactory(scheme_account=mcard1, user=trusted_user1)
        user1_mcard_entry = SchemeAccountEntryFactory(scheme_account=mcard1, user=user1)
        user2_mcard_entry = SchemeAccountEntryFactory(scheme_account=mcard1, user=user2)

        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, trusted_user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user2)

        mock_send_message.call_count = 0
        user1_channel = user1.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id
        user2_channel = user2.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id

        # TEST
        deleted_membership_card_cleanup(
            user1_mcard_entry,
            arrow.utcnow().format(),
            channel_slug=user1_channel,
        )

        # dw user pll status change event -> dw remove loyalty card event
        self.assertEqual(2, mock_send_message.call_count)
        mock_send_message.call_count = 0

        deleted_membership_card_cleanup(
            user2_mcard_entry,
            arrow.utcnow().format(),
            channel_slug=user2_channel,
        )

        expected_msg_body = {}
        expected_msg_headers = {
            "X-azure-ref": None,
            "bink-user-id": str(user2.id),
            "channel": user2_channel,
            "loyalty-plan": mcard1.scheme.slug,
            "request-id": str(mcard1.id),
            # "transaction-id": "5479d204-6da8-11ee-af1c-3af9d391be47",
            "type": "loyalty_card.removed.bink",
        }

        # dw user pll status change event -> dw remove loyalty card event -> this midas loyalty card removed event
        self.assertEqual(3, mock_send_message.call_count)

        call_args = mock_send_message.call_args_list[-1]
        self.assertEqual((expected_msg_body,), call_args.args)
        # check if expected_message_headers is a subset of headers. Full headers will have a random transaction id.
        self.assertEqual(call_args.kwargs["headers"], call_args.kwargs["headers"] | expected_msg_headers)
        self.assertIn("transaction-id", call_args.kwargs["headers"])

    @patch("message_lib.producer.MessageProducer._MessageProducerQueueHandler.send_message")
    def test_loyalty_card_removed_event_sent_when_deleting_user_trusted_channel(self, mock_send_message):
        """
        A LoyaltyCardRemoved (trusted channel) event should be sent when the last payment card in a retailer
        (trusted) channel is unlinked from a loyalty card.

        This test is when the unlinking happens specifically when a user is deleted.
        """
        trusted_user1 = self.trusted_channel_user()
        external_id_1 = "testuser@testbink.com"
        user1 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user2 = UserFactory(external_id=external_id_2, email=external_id_2)

        # Add an Active payment account and link mcard to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=trusted_user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)

        # Add scheme account to all users
        mcard1 = SchemeAccountFactory(card_number="1111")

        SchemeAccountEntryFactory(scheme_account=mcard1, user=trusted_user1)
        SchemeAccountEntryFactory(scheme_account=mcard1, user=user1)
        SchemeAccountEntryFactory(scheme_account=mcard1, user=user2)

        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, trusted_user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user2)

        mock_send_message.call_count = 0
        trusted_user1_channel = trusted_user1.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id

        # TEST
        deleted_service_cleanup(user_id=trusted_user1.id, consent={}, channel_slug=trusted_user1_channel)

        expected_msg_body = {}
        expected_msg_headers = {
            "X-azure-ref": None,
            "bink-user-id": str(trusted_user1.id),
            "channel": trusted_user1_channel,
            "loyalty-plan": mcard1.scheme.slug,
            "request-id": str(mcard1.id),
            # "transaction-id": "5479d204-6da8-11ee-af1c-3af9d391be47",
            "type": "loyalty_card.removed.bink",
        }

        # dw user pll status change event -> dw remove loyalty card event -> this midas loyalty card removed event
        # -> dw payment card removed event
        self.assertEqual(4, mock_send_message.call_count)

        call_args = mock_send_message.call_args_list[-2]
        self.assertEqual((expected_msg_body,), call_args.args)
        # check if expected_message_headers is a subset of headers. Full headers will have a random transaction id.
        self.assertEqual(call_args.kwargs["headers"], call_args.kwargs["headers"] | expected_msg_headers)
        self.assertIn("transaction-id", call_args.kwargs["headers"])

    @patch("message_lib.producer.MessageProducer._MessageProducerQueueHandler.send_message")
    def test_loyalty_card_removed_event_sent_when_deleting_user_non_trusted_channel(self, mock_send_message):
        """
        A LoyaltyCardRemoved (non-trusted channel) event should be sent when the last payment card in a
        channel is unlinked from a loyalty card AND there are no other non-trusted channels that hold a link
        for the given loyalty card.

        This test is for when the unlinking happens specifically when a user is deleted.
        """
        trusted_user1 = self.trusted_channel_user()
        external_id_1 = "testuser@testbink.com"
        user1 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user2 = UserFactory(external_id=external_id_2, email=external_id_2)

        # Add an Active payment account and link mcard to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=trusted_user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)

        # Add scheme account to all users
        mcard1 = SchemeAccountFactory()

        SchemeAccountEntryFactory(scheme_account=mcard1, user=trusted_user1)
        SchemeAccountEntryFactory(scheme_account=mcard1, user=user1)
        SchemeAccountEntryFactory(scheme_account=mcard1, user=user2)

        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, trusted_user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user2)

        mock_send_message.call_count = 0
        user1_channel = user1.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id
        user2_channel = user2.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id

        # TEST
        deleted_service_cleanup(user_id=user1.id, consent={}, channel_slug=user1_channel)

        # dw user pll status change event -> dw remove loyalty card event -> payment card removed
        self.assertEqual(3, mock_send_message.call_count)
        mock_send_message.call_count = 0

        deleted_service_cleanup(user_id=user2.id, consent={}, channel_slug=user2_channel)

        expected_msg_body = {}
        expected_msg_headers = {
            "X-azure-ref": None,
            "bink-user-id": str(user2.id),
            "channel": user2_channel,
            "loyalty-plan": mcard1.scheme.slug,
            "request-id": str(mcard1.id),
            # "transaction-id": "5479d204-6da8-11ee-af1c-3af9d391be47",
            "type": "loyalty_card.removed.bink",
        }

        # dw user pll status change event -> dw remove loyalty card event -> this midas loyalty card removed event
        # -> dw payment card removed event
        self.assertEqual(4, mock_send_message.call_count)

        call_args = mock_send_message.call_args_list[-2]
        self.assertEqual((expected_msg_body,), call_args.args)
        # check if expected_message_headers is a subset of headers. Full headers will have a random transaction id.
        self.assertEqual(call_args.kwargs["headers"], call_args.kwargs["headers"] | expected_msg_headers)
        self.assertIn("transaction-id", call_args.kwargs["headers"])

    @patch("message_lib.producer.MessageProducer._MessageProducerQueueHandler.send_message")
    def test_loyalty_card_removed_event_sent_when_user_pll_status_change_trusted_channel(self, mock_send_message):
        """
        A LoyaltyCardRemoved (trusted channel) event should be sent when the last payment card in a retailer
        (trusted) channel is unlinked from a loyalty card.

        This test is for when the unlinking happens specifically when the User PLL state changes from Active
        to a non-active status i.e via a loyalty card changing from Active to an error state.
        """
        trusted_user1 = self.trusted_channel_user()
        external_id_1 = "testuser@testbink.com"
        user1 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user2 = UserFactory(external_id=external_id_2, email=external_id_2)

        # Add an Active payment account and link mcard to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=trusted_user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)

        # Add scheme account to all users
        mcard1 = SchemeAccountFactory(card_number="1111")

        tc_user_mcard_entry = SchemeAccountEntryFactory(scheme_account=mcard1, user=trusted_user1)
        SchemeAccountEntryFactory(scheme_account=mcard1, user=user1)
        SchemeAccountEntryFactory(scheme_account=mcard1, user=user2)

        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, trusted_user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user2)

        trusted_user1_channel = trusted_user1.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id

        # TEST
        # todo: add proper parameterization for django tests
        for status in (AccountLinkStatus.SERVICE_CONNECTION_ERROR, AccountLinkStatus.INVALID_CREDENTIALS):
            if tc_user_mcard_entry.link_status != AccountLinkStatus.ACTIVE:
                tc_user_mcard_entry.link_status = AccountLinkStatus.ACTIVE
                tc_user_mcard_entry.save(update_fields=["link_status"])

            mock_send_message.call_count = 0
            # trigger SchemeAccountEntry signal
            tc_user_mcard_entry.link_status = status
            tc_user_mcard_entry.save(update_fields=["link_status"])

            expected_msg_body = {}
            expected_msg_headers = {
                "X-azure-ref": None,
                "bink-user-id": str(trusted_user1.id),
                "channel": trusted_user1_channel,
                "loyalty-plan": mcard1.scheme.slug,
                "request-id": str(mcard1.id),
                # "transaction-id": "5479d204-6da8-11ee-af1c-3af9d391be47",
                "type": "loyalty_card.removed.bink",
            }

            # dw user pll status change event -> this midas loyalty card removed event
            self.assertEqual(2, mock_send_message.call_count)

            call_args = mock_send_message.call_args_list[-1]
            self.assertEqual((expected_msg_body,), call_args.args)
            # check if expected_message_headers is a subset of headers. Full headers will have a random transaction id.
            self.assertEqual(call_args.kwargs["headers"], call_args.kwargs["headers"] | expected_msg_headers)
            self.assertIn("transaction-id", call_args.kwargs["headers"])

    @patch("message_lib.producer.MessageProducer._MessageProducerQueueHandler.send_message")
    def test_loyalty_card_removed_event_sent_when_user_pll_status_change_non_trusted_channel(self, mock_send_message):
        """
        A LoyaltyCardRemoved (non-trusted channel) event should be sent when the last payment card in a
        channel is unlinked from a loyalty card AND there are no other non-trusted channels that hold a link
        for the given loyalty card.

        This test is for when the unlinking happens specifically when the User PLL state changes from Active
        to a non-active status i.e via a loyalty card changing from Active to an error state.
        """
        trusted_user1 = self.trusted_channel_user()
        external_id_1 = "testuser@testbink.com"
        user1 = UserFactory(external_id=external_id_1, email=external_id_1)
        external_id_2 = "testuser2@testbink.com"
        user2 = UserFactory(external_id=external_id_2, email=external_id_2)

        # Add an Active payment account and link mcard to test PLL link handling
        payment_card = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=trusted_user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user1, payment_card_account=payment_card)
        PaymentCardAccountEntryFactory(user=user2, payment_card_account=payment_card)

        # Add scheme account to all users
        mcard1 = SchemeAccountFactory()

        SchemeAccountEntryFactory(scheme_account=mcard1, user=trusted_user1)
        user1_mcard_entry = SchemeAccountEntryFactory(scheme_account=mcard1, user=user1)
        user2_mcard_entry = SchemeAccountEntryFactory(scheme_account=mcard1, user=user2)

        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, trusted_user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user1)
        PllUserAssociation.link_users_scheme_account_to_payment(mcard1, payment_card, user2)

        user1.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id  # noqa: B018
        user2_channel = user2.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id

        # TEST
        # todo: add proper parameterization for django tests
        for status in (AccountLinkStatus.SERVICE_CONNECTION_ERROR, AccountLinkStatus.INVALID_CREDENTIALS):
            mock_send_message.call_count = 0
            # trigger SchemeAccountEntry signal
            user1_mcard_entry.link_status = status
            user1_mcard_entry.save(update_fields=["link_status"])

            # dw pll status change sent but not this event
            self.assertEqual(1, mock_send_message.call_count)

            mock_send_message.call_count = 0
            user2_mcard_entry.link_status = status
            user2_mcard_entry.save(update_fields=["link_status"])

            expected_msg_body = {}
            expected_msg_headers = {
                "X-azure-ref": None,
                "bink-user-id": str(user2.id),
                "channel": user2_channel,
                "loyalty-plan": mcard1.scheme.slug,
                "request-id": str(mcard1.id),
                # "transaction-id": "5479d204-6da8-11ee-af1c-3af9d391be47",
                "type": "loyalty_card.removed.bink",
            }

            # dw user pll status change event -> this midas loyalty card removed event
            self.assertEqual(2, mock_send_message.call_count)

            call_args = mock_send_message.call_args_list[-1]
            self.assertEqual((expected_msg_body,), call_args.args)
            # check if expected_message_headers is a subset of headers. Full headers will have a random transaction id.
            self.assertEqual(call_args.kwargs["headers"], call_args.kwargs["headers"] | expected_msg_headers)
            self.assertIn("transaction-id", call_args.kwargs["headers"])

            # Reset link statuses to active for the next iteration. This should be removed when proper
            # parameterization is added.
            if user1_mcard_entry.link_status != AccountLinkStatus.ACTIVE:
                user1_mcard_entry.link_status = AccountLinkStatus.ACTIVE
                user1_mcard_entry.save(update_fields=["link_status"])

            if user2_mcard_entry.link_status != AccountLinkStatus.ACTIVE:
                user2_mcard_entry.link_status = AccountLinkStatus.ACTIVE
                user2_mcard_entry.save(update_fields=["link_status"])

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
        user1_channel = user1.client.clientapplicationbundle_set.only("bundle_id").first().bundle_id
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

        deleted_payment_card_cleanup(payment_card.id, None, user_id=user2.id, channel_slug=user1_channel)

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

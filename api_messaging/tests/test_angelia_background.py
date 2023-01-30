from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.test import override_settings

from api_messaging.angelia_background import (
    loyalty_card_add,
    loyalty_card_join,
    loyalty_card_register,
    post_payment_account,
    refresh_balances,
)
from history.utils import GlobalMockAPITestCase
from payment_card.models import PaymentCardAccount
from payment_card.tests.factories import IssuerFactory, PaymentCardAccountFactory, PaymentCardFactory
from scheme.credentials import EMAIL, POSTCODE
from scheme.models import SchemeAccount, SchemeBundleAssociation, SchemeCredentialQuestion
from scheme.tests.factories import (
    SchemeAccountFactory,
    SchemeBalanceDetailsFactory,
    SchemeBundleAssociationFactory,
    SchemeFactory,
)
from ubiquity.models import (
    AccountLinkStatus,
    PaymentCardSchemeEntry,
    PllUserAssociation,
    WalletPLLSlug,
    WalletPLLStatus,
)
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory
from user.tests.factories import (
    ClientApplicationBundleFactory,
    ClientApplicationFactory,
    OrganisationFactory,
    UserFactory,
)

# @todo Convert this to automatic testing by removing word manual from file name.  Seems something is left set which
# breaks other test cases.  Requires further investigation and possible fix of code.


class MockMidasBalanceResponse:
    def __init__(self, status_code=200, balance=None, pending=False):
        self.status_code = status_code
        if balance is None:
            self.json_body = {
                "value": Decimal("10"),
                "points": Decimal("100"),
                "points_label": "100",
                "value_label": "$10",
                "reward_tier": 0,
                "balance": Decimal("20"),
                "is_stale": False,
                "pending": pending,
            }
        else:
            self.json_body = {"is_stale": False, "pending": pending}
            self.json_body.update(balance)

    def json(self) -> dict:
        return self.json_body


class TestAngeliaBackground(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        organisation = OrganisationFactory(name="test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=organisation,
            name="set up client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)
        external_id = "test@user.com"
        external_id2 = "test2@user.com"
        cls.user = UserFactory(external_id=external_id, client=cls.client_app, email=external_id)
        cls.user2 = UserFactory(external_id=external_id2, client=cls.client_app, email=external_id2)
        cls.scheme = SchemeFactory()
        SchemeBalanceDetailsFactory(scheme_id=cls.scheme)
        # SchemeCredentialQuestionFactory(scheme=cls.scheme, type=CARD_NUMBER)
        # Need to add an active association since it was assumed no setting was enabled
        cls.scheme_bundle_association = SchemeBundleAssociationFactory(
            scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        cls.issuer = IssuerFactory(name="Barclays")
        cls.payment_card = PaymentCardFactory(slug="visa", system="visa")
        cls.pcard_hash1 = "some_hash"
        cls.pcard_hash2 = "5ae741975b4db7bc80072fe8f88f233ef4a67e1e1d7e3bbf68a314dfc6691636"

        cls.auth_service_headers = {"HTTP_AUTHORIZATION": "Token " + settings.SERVICE_API_KEY}

    def setUp(self) -> None:
        self.payment_card_account = PaymentCardAccountFactory(
            issuer=self.issuer, payment_card=self.payment_card, hash=self.pcard_hash2, status=PaymentCardAccount.ACTIVE
        )
        self.payment_card_account_entry = PaymentCardAccountEntryFactory(
            user=self.user, payment_card_account=self.payment_card_account
        )

        self.scheme_account = SchemeAccountFactory(scheme=self.scheme)

        self.scheme_account_entry = SchemeAccountEntryFactory.create(scheme_account=self.scheme_account, user=self.user)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch.object(SchemeAccount, "_get_balance")
    def test_angelia_background_refresh(self, mock_get_midas_response):
        """
        Using angelia background request to refresh balance for a user and bundle_id

        """
        test_scheme_account = SchemeAccountFactory(scheme=self.scheme)
        test_scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=test_scheme_account, user=self.user2, link_status=AccountLinkStatus.ACTIVE
        )

        PaymentCardAccountEntryFactory(user=self.user2, payment_card_account=self.payment_card_account)

        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            payment_card_accounts=[self.payment_card_account], scheme_account=self.scheme_account, user=self.user
        )

        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            payment_card_accounts=[self.payment_card_account], scheme_account=test_scheme_account, user=self.user2
        )

        # All accounts will get same balance response
        mock_get_midas_response.return_value = MockMidasBalanceResponse(200)

        refresh_balance_message = {
            "user_id": self.user.id,
            "channel_slug": self.bundle.bundle_id,
        }
        user_pll = PllUserAssociation.objects.get(pll__scheme_account=self.scheme_account, user=self.user)
        user_pll2 = PllUserAssociation.objects.get(pll__scheme_account=test_scheme_account, user=self.user2)
        self.assertFalse(test_scheme_account.balances)
        self.assertFalse(self.scheme_account.balances)

        refresh_balances(refresh_balance_message)

        test_scheme_account.refresh_from_db()
        self.scheme_account.refresh_from_db()
        test_scheme_account_entry.refresh_from_db()
        self.scheme_account_entry.refresh_from_db()
        self.assertTrue(mock_get_midas_response.called)
        self.assertFalse(test_scheme_account.balances)
        self.assertTrue(self.scheme_account.balances)
        self.assertEqual(test_scheme_account_entry.link_status, AccountLinkStatus.ACTIVE)
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.ACTIVE)

        self.assertEqual("", user_pll.slug)
        self.assertEqual(WalletPLLStatus.ACTIVE, user_pll.state)
        self.assertTrue(user_pll.pll.active_link)

        self.assertEqual(WalletPLLSlug.UBIQUITY_COLLISION.value, user_pll2.slug)
        self.assertEqual(WalletPLLStatus.INACTIVE, user_pll2.state)
        self.assertFalse(user_pll2.pll.active_link)

        refresh_balance_message = {
            "user_id": self.user2.id,
            "channel_slug": self.bundle.bundle_id,
        }

        refresh_balances(refresh_balance_message)
        test_scheme_account.refresh_from_db()
        self.scheme_account.refresh_from_db()
        test_scheme_account_entry.refresh_from_db()
        self.scheme_account_entry.refresh_from_db()
        user_pll.refresh_from_db()
        user_pll2.refresh_from_db()
        self.assertTrue(mock_get_midas_response.called)
        self.assertTrue(test_scheme_account.balances)
        self.assertTrue(self.scheme_account.balances)
        self.assertEqual(test_scheme_account_entry.link_status, AccountLinkStatus.ACTIVE)
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.ACTIVE)

        self.assertEqual("", user_pll.slug)
        self.assertEqual(WalletPLLStatus.ACTIVE, user_pll.state)
        self.assertTrue(user_pll.pll.active_link)

        self.assertEqual(WalletPLLSlug.UBIQUITY_COLLISION.value, user_pll2.slug)
        self.assertEqual(WalletPLLStatus.INACTIVE, user_pll2.state)
        self.assertFalse(user_pll2.pll.active_link)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("api_messaging.midas_messaging.to_midas", autospec=True)
    def test_loyalty_card_join_valid(self, mock_midas_send):
        """
        This test is for angelia background "loyalty_card_join" message handler - testing complete route through to
        midas message send via Q.
        """
        SchemeCredentialQuestion.objects.create(scheme=self.scheme, type=EMAIL, manual_question=True, label="Email")

        self.scheme_account_entry.link_status = AccountLinkStatus.PENDING
        self.scheme_account_entry.save()

        loyalty_card_join(
            {
                "loyalty_plan_id": self.scheme.id,
                "loyalty_card_id": self.scheme_account.id,
                "entry_id": self.scheme_account_entry.id,
                "user_id": self.user.id,
                "channel_slug": self.bundle.bundle_id,
                "journey": "JOIN",
                "auto_link": True,
                "join_fields": [{"credential_slug": "email", "value": "qatest+testnp2join1201@bink.com"}],
                "consents": [],
            }
        )

        self.assertTrue(mock_midas_send.called)
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.PENDING)
        user_pll = PllUserAssociation.objects.get(pll__scheme_account=self.scheme_account, user=self.user)
        self.assertEqual(user_pll.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll.slug, WalletPLLSlug.LOYALTY_CARD_PENDING.value)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("api_messaging.midas_messaging.to_midas", autospec=True)
    def test_loyalty_card_join_invalid_email(self, mock_midas_send):
        """
        This test is for angelia background "loyalty_card_join" message handler - testing complete route through to
        midas message send via Q.

        This test relates to a buf LOY-2883 - No pll when payment card added first and join in progress has an invalid
        email

        """

        SchemeCredentialQuestion.objects.create(scheme=self.scheme, type=EMAIL, manual_question=True, label="Email")

        self.scheme_account_entry.link_status = AccountLinkStatus.PENDING
        self.scheme_account_entry.save()

        loyalty_card_join(
            {
                "loyalty_plan_id": self.scheme.id,
                "loyalty_card_id": self.scheme_account.id,
                "entry_id": self.scheme_account_entry.id,
                "user_id": self.user.id,
                "channel_slug": self.bundle.bundle_id,
                "journey": "JOIN",
                "auto_link": True,
                "join_fields": [{"credential_slug": "email", "value": "qatest+testnp2join1201bink.com"}],
                "consents": [],
            }
        )

        self.assertFalse(mock_midas_send.called)
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.INVALID_CREDENTIALS)
        user_pll = PllUserAssociation.objects.get(pll__scheme_account=self.scheme_account, user=self.user)
        self.assertEqual(user_pll.state, WalletPLLStatus.INACTIVE.value)
        self.assertEqual(user_pll.slug, WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch.object(SchemeAccount, "_get_balance")
    @patch("api_messaging.midas_messaging.to_midas", autospec=True)
    def test_payment_card_pending_and_loyalty_card_join_valid(self, mock_midas_send, mock_get_midas_response):
        """
        This test is for angelia background "loyalty_card_join" message handler when there is a pending
        payment card - testing complete route through to midas message send via Q.
         Then tests the Midas call back of status change

        Relates to LOY-2882: Incorrect PLL status
        """
        self.payment_card_account.status = PaymentCardAccount.PENDING
        self.payment_card_account.save()

        SchemeCredentialQuestion.objects.create(scheme=self.scheme, type=EMAIL, manual_question=True, label="Email")

        self.scheme_account_entry.link_status = AccountLinkStatus.PENDING
        self.scheme_account_entry.save()

        loyalty_card_join(
            {
                "loyalty_plan_id": self.scheme.id,
                "loyalty_card_id": self.scheme_account.id,
                "entry_id": self.scheme_account_entry.id,
                "user_id": self.user.id,
                "channel_slug": self.bundle.bundle_id,
                "journey": "JOIN",
                "auto_link": True,
                "join_fields": [{"credential_slug": "email", "value": "qatest+testnp2join1201@bink.com"}],
                "consents": [],
            }
        )

        self.assertTrue(mock_midas_send.called)
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.PENDING)
        user_pll = PllUserAssociation.objects.get(pll__scheme_account=self.scheme_account, user=self.user)
        self.assertEqual(user_pll.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll.slug, WalletPLLSlug.PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING.value)

        # Now verify the call back from midas
        mock_get_midas_response.return_value = MockMidasBalanceResponse(200)
        data = {
            "status": AccountLinkStatus.ACTIVE,
            "journey": "join",
            "user_info": {"bink_user_id": self.user.id},
        }
        response = self.client.post(
            "/schemes/accounts/{}/status/".format(self.scheme_account.id),
            data,
            format="json",
            **self.auth_service_headers
        )
        self.assertTrue(mock_get_midas_response.called)
        self.assertEqual(response.status_code, 200)
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.ACTIVE)
        user_pll.refresh_from_db()
        self.assertEqual(user_pll.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch.object(SchemeAccount, "_get_balance")
    @patch("api_messaging.midas_messaging.to_midas", autospec=True)
    def test_payment_card_active_and_loyalty_card_join_valid(self, mock_midas_send, mock_get_midas_response):
        """
        This test is for angelia background "loyalty_card_join" message handler when there is a pending
        payment card - testing complete route through to midas message send via Q.
        Then tests the Midas call back of status change
        """

        SchemeCredentialQuestion.objects.create(scheme=self.scheme, type=EMAIL, manual_question=True, label="Email")
        self.scheme_account_entry.link_status = AccountLinkStatus.PENDING
        self.scheme_account_entry.save()

        loyalty_card_join(
            {
                "loyalty_plan_id": self.scheme.id,
                "loyalty_card_id": self.scheme_account.id,
                "entry_id": self.scheme_account_entry.id,
                "user_id": self.user.id,
                "channel_slug": self.bundle.bundle_id,
                "journey": "JOIN",
                "auto_link": True,
                "join_fields": [{"credential_slug": "email", "value": "qatest+testnp2join1201@bink.com"}],
                "consents": [],
            }
        )

        self.assertTrue(mock_midas_send.called)
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.PENDING)
        user_pll = PllUserAssociation.objects.get(pll__scheme_account=self.scheme_account, user=self.user)
        self.assertEqual(user_pll.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll.slug, WalletPLLSlug.LOYALTY_CARD_PENDING.value)

        # Now verify the call back from midas
        mock_get_midas_response.return_value = MockMidasBalanceResponse(200)
        data = {
            "status": AccountLinkStatus.ACTIVE,
            "journey": "join",
            "user_info": {"bink_user_id": self.user.id},
        }
        response = self.client.post(
            "/schemes/accounts/{}/status/".format(self.scheme_account.id),
            data,
            format="json",
            **self.auth_service_headers
        )
        self.assertTrue(mock_get_midas_response.called)
        self.assertEqual(response.status_code, 200)
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.ACTIVE)
        user_pll.refresh_from_db()
        self.assertEqual(user_pll.state, WalletPLLStatus.ACTIVE.value)
        self.assertEqual(user_pll.slug, "")

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch.object(SchemeAccount, "_get_balance")
    @patch("api_messaging.midas_messaging.to_midas", autospec=True)
    @patch.object(PaymentCardSchemeEntry, "vop_activate_check", autospec=True)
    def test_payment_card_active_and_loyalty_card_register_valid(
        self, mock_vop_check, mock_midas_send, mock_get_midas_response
    ):
        """
        This test is for angelia background "loyalty_card_join" message handler when there is a pending
        payment card - testing complete route through to midas message send via Q.
        Then tests the Midas call back of status change
        """

        SchemeCredentialQuestion.objects.create(
            scheme=self.scheme, type=POSTCODE, manual_question=True, label="PostCode"
        )

        self.scheme_account.card_number = "1234"
        self.scheme_account.save()

        self.scheme_account_entry.link_status = AccountLinkStatus.PENDING
        self.scheme_account_entry.save()

        loyalty_card_register(
            {
                "loyalty_plan_id": self.scheme.id,
                "loyalty_card_id": self.scheme_account.id,
                "entry_id": self.scheme_account_entry.id,
                "user_id": self.user.id,
                "channel_slug": self.bundle.bundle_id,
                "journey": "REGISTER",
                "auto_link": True,
                "register_fields": [{"credential_slug": "postcode", "value": "GU22TT"}],
                "consents": [],
            }
        )

        self.assertTrue(mock_midas_send.called)
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.REGISTRATION_ASYNC_IN_PROGRESS)
        user_pll = PllUserAssociation.objects.get(pll__scheme_account=self.scheme_account, user=self.user)
        self.assertEqual(user_pll.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll.slug, WalletPLLSlug.LOYALTY_CARD_PENDING.value)

        # Now verify the call back from midas
        mock_get_midas_response.return_value = MockMidasBalanceResponse(200)
        data = {
            "status": AccountLinkStatus.ACTIVE,
            "journey": "register",
            "user_info": {"bink_user_id": self.user.id},
        }
        response = self.client.post(
            "/schemes/accounts/{}/status/".format(self.scheme_account.id),
            data,
            format="json",
            **self.auth_service_headers
        )
        self.assertTrue(mock_vop_check.called)
        self.assertFalse(mock_get_midas_response.called)
        self.assertEqual(response.status_code, 200)
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.ACTIVE)
        user_pll.refresh_from_db()
        self.assertTrue(user_pll.pll.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.ACTIVE.value)
        self.assertEqual(user_pll.slug, "")

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch.object(SchemeAccount, "_get_balance")
    @patch("api_messaging.midas_messaging.to_midas", autospec=True)
    @patch.object(PaymentCardSchemeEntry, "vop_activate_check", autospec=True)
    def test_payment_card_pending_and_loyalty_card_register_valid(
        self, mock_vop_check, mock_midas_send, mock_get_midas_response
    ):
        """
        This test is for angelia background "loyalty_card_join" message handler when there is a pending
        payment card - testing complete route through to midas message send via Q.
        Then tests the Midas call back of status change
        """

        SchemeCredentialQuestion.objects.create(
            scheme=self.scheme, type=POSTCODE, manual_question=True, label="PostCode"
        )

        self.scheme_account.card_number = "1234"
        self.scheme_account.save()

        self.scheme_account_entry.link_status = AccountLinkStatus.PENDING
        self.scheme_account_entry.save()

        self.payment_card_account.status = PaymentCardAccount.PENDING
        self.payment_card_account.save()

        loyalty_card_register(
            {
                "loyalty_plan_id": self.scheme.id,
                "loyalty_card_id": self.scheme_account.id,
                "entry_id": self.scheme_account_entry.id,
                "user_id": self.user.id,
                "channel_slug": self.bundle.bundle_id,
                "journey": "REGISTER",
                "auto_link": True,
                "register_fields": [{"credential_slug": "postcode", "value": "GU22TT"}],
                "consents": [],
            }
        )

        self.assertTrue(mock_midas_send.called)
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.REGISTRATION_ASYNC_IN_PROGRESS)
        user_pll = PllUserAssociation.objects.get(pll__scheme_account=self.scheme_account, user=self.user)
        self.assertEqual(user_pll.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll.slug, WalletPLLSlug.PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING.value)

        # Now verify the call back from midas
        mock_get_midas_response.return_value = MockMidasBalanceResponse(200)
        data = {
            "status": AccountLinkStatus.ACTIVE,
            "journey": "register",
            "user_info": {"bink_user_id": self.user.id},
        }
        response = self.client.post(
            "/schemes/accounts/{}/status/".format(self.scheme_account.id),
            data,
            format="json",
            **self.auth_service_headers
        )
        self.assertFalse(mock_vop_check.called)
        self.assertFalse(mock_get_midas_response.called)
        self.assertEqual(response.status_code, 200)
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.ACTIVE)
        user_pll.refresh_from_db()
        self.assertFalse(user_pll.pll.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch.object(SchemeAccount, "_get_balance")
    def test_duplicate_cards_in_2_wallets(self, mock_get_midas_response):
        """
        This test uses angelia background calls to loyalty_card_add and loyalty_card_add and tests the wallet
        setup with Mock midas get balance reply. The order is loyalty_card_add first
        The focus is on the angelia background logic when duplicate payment and scheme accounts are
        linked in two wallets.
        Note a bug was reported which might implies this did not work correctly for API 2.0

        Error reported in LOY-2874
        expected result: wallet1 has PLL status = PAYMENT_ACCOUNT_PENDING  wallet2 = LOYALTY_CARD_NOT_AUTHORISED

        Steps to reproduce from API:
        1. In Wallet_1 add and auth iceland card.
        2. In Wallet_1 add Pending payment card with token ERRRET_500
        3. GET /wallet. PLL link shows PAYMENT_ACCOUNT_PENDING as expected.
        4. In Wallet_2 add Wallet_only card from step 1 (with only add credentials).
            Or add and auth the same iceland card from step 1(with add and auth credentials).
        5. Add the same pending card from step 2 in Wallet_2
        6. GET /wallet. (Wallet_2) PLL link shows LOYALTY_CARD_NOT_AUTHORISED as expected in the second wallet
        7. Call Get wallet_1 again. PLL in Wallet_1 is updated and
          now shows LOYALTY_CARD_NOT_AUTHORISED instead of PAYMENT_ACCOUNT_PENDING.

        This test sets up wallet 1 in db
        Then uses Angelia background calls to set up Wallet2
        Verifies that refresh does not change state.
        """

        # 1 to 3 - check wallet 1 is set up - user pll expected as PAYMENT_ACCOUNT_PENDING

        self.payment_card_account.status = PaymentCardAccount.PENDING
        self.payment_card_account.save()

        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            payment_card_accounts=[self.payment_card_account], scheme_account=self.scheme_account, user=self.user
        )
        user_pll_1 = PllUserAssociation.objects.get(pll__scheme_account=self.scheme_account, user=self.user)

        self.assertEqual(user_pll_1.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)

        # Step 4 add same scheme account to Wallet2
        scheme_account_entry_2 = SchemeAccountEntryFactory.create(scheme_account=self.scheme_account, user=self.user2)
        scheme_account_entry_2.link_status = AccountLinkStatus.WALLET_ONLY
        # save - triggers a POST save but does not call pll linking because update_fields not set
        scheme_account_entry_2.save()

        # Step 4 add same scheme account to Wallet2 using angelia call back will not link anything because
        # no payment card in wallet
        loyalty_card_add(
            {
                "entry_id": scheme_account_entry_2.id,
                "user_id": self.user2.id,
                "channel_slug": self.bundle.bundle_id,
                "auto_link": True,
                "add_fields": [{"credential_slug": "card_number", "value": "3038401022657083"}],
            }
        )

        # Step 5 add same payment card  linked to user2  (Wallet2) then pll link using angelia_background task
        PaymentCardAccountEntryFactory(user=self.user2, payment_card_account=self.payment_card_account).save()

        post_payment_account(
            {
                "payment_account_id": self.payment_card_account.id,
                "user_id": self.user2.id,
                "channel_slug": self.bundle.bundle_id,
                "auto_link": True,
                "created": False,
            }
        )

        user_pll_1.refresh_from_db()
        user_pll_2 = PllUserAssociation.objects.get(pll__scheme_account=self.scheme_account, user=self.user2)
        self.assertEqual(user_pll_1.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)
        self.assertEqual(user_pll_2.state, WalletPLLStatus.INACTIVE.value)
        self.assertEqual(user_pll_2.slug, WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)

        mock_get_midas_response.return_value = MockMidasBalanceResponse(200)
        # refresh all balances as user2 which is wallet only so balance is not called
        refresh_balances(
            {
                "user_id": self.user2.id,
                "channel_slug": self.bundle.bundle_id,
            }
        )
        self.assertFalse(mock_get_midas_response.called)

        # refresh all balances as user1 balance is not called - check status unchanged
        refresh_balances(
            {
                "user_id": self.user.id,
                "channel_slug": self.bundle.bundle_id,
            }
        )
        self.assertTrue(mock_get_midas_response.called)

        user_pll_1.refresh_from_db()
        user_pll_2.refresh_from_db()
        self.assertEqual(user_pll_1.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)
        self.assertEqual(user_pll_2.state, WalletPLLStatus.INACTIVE.value)
        self.assertEqual(user_pll_2.slug, WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch.object(SchemeAccount, "_get_balance")
    def test_duplicate_cards_in_pay_last_2_wallets(self, mock_get_midas_response):
        """
        This test uses angelia background calls to loyalty_card_add and post_payment_account and tests the wallet
        setup with Mock midas get balance reply.  The order is post_payment_account first
        The focus is on angelia background logic when duplicate payment and scheme accounts are
        linked in two wallets.
        Note a bug was reported which might implies this did not work correctly.

        Error reported in LOY-2874 switching steps 4 and 5  ie Payment then Loyalty
        expected result: wallet1 has PLL status = PAYMENT_ACCOUNT_PENDING  wallet2 = LOYALTY_CARD_NOT_AUTHORISED

        Steps to reproduce from API:
        1. In Wallet_1 add and auth iceland card.
        2. In Wallet_1 add Pending payment card with token ERRRET_500
        3. GET /wallet. PLL link shows PAYMENT_ACCOUNT_PENDING as expected.
        4. Add the same pending card from step 2 in Wallet_2
        5. In Wallet_2 add Wallet_only card from step 1 (with only add credentials).
            Or add and auth the same iceland card from step 1(with add and auth credentials).

        6. GET /wallet. (Wallet_2) PLL link shows LOYALTY_CARD_NOT_AUTHORISED as expected in the second wallet
        7. Call Get wallet_1 again. PLL in Wallet_1 is updated and
          now shows LOYALTY_CARD_NOT_AUTHORISED instead of PAYMENT_ACCOUNT_PENDING.

        This test sets up wallet 1 in db
        Then uses Angelia background calls to set up Wallet2
        Verifies that refresh does not change state.
        """

        # 1 to 3 - check wallet 1 is set up - user pll expected as PAYMENT_ACCOUNT_PENDING

        self.payment_card_account.status = PaymentCardAccount.PENDING
        self.payment_card_account.save()

        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            payment_card_accounts=[self.payment_card_account], scheme_account=self.scheme_account, user=self.user
        )
        user_pll_1 = PllUserAssociation.objects.get(pll__scheme_account=self.scheme_account, user=self.user)

        self.assertEqual(user_pll_1.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)

        # Step 4 add same payment card to Wallet2 (user 2) using angelia_background task called by Angelia
        # This does not call Metis as payment card is created and pending

        PaymentCardAccountEntryFactory(user=self.user2, payment_card_account=self.payment_card_account).save()
        post_payment_account(
            {
                "payment_account_id": self.payment_card_account.id,
                "user_id": self.user2.id,
                "channel_slug": self.bundle.bundle_id,
                "auto_link": True,
                "created": False,
            }
        )

        # Step 5 add same scheme account to Wallet2
        scheme_account_entry_2 = SchemeAccountEntryFactory.create(scheme_account=self.scheme_account, user=self.user2)
        scheme_account_entry_2.link_status = AccountLinkStatus.WALLET_ONLY
        # save - triggers a POST save but does not call pll linking because update_fields not set
        scheme_account_entry_2.save()

        # Step 5 add same scheme account to Wallet2 using angelia call back will link payment card in wallet
        loyalty_card_add(
            {
                "entry_id": scheme_account_entry_2.id,
                "user_id": self.user2.id,
                "channel_slug": self.bundle.bundle_id,
                "auto_link": True,
                "add_fields": [{"credential_slug": "card_number", "value": "3038401022657083"}],
            }
        )

        user_pll_1.refresh_from_db()
        user_pll_2 = PllUserAssociation.objects.get(pll__scheme_account=self.scheme_account, user=self.user2)
        self.assertEqual(user_pll_1.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)
        self.assertEqual(user_pll_2.state, WalletPLLStatus.INACTIVE.value)
        self.assertEqual(user_pll_2.slug, WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)

        mock_get_midas_response.return_value = MockMidasBalanceResponse(200)
        # refresh all balances as user2 which is wallet only so balance is not called
        refresh_balances(
            {
                "user_id": self.user2.id,
                "channel_slug": self.bundle.bundle_id,
            }
        )
        self.assertFalse(mock_get_midas_response.called)

        # refresh all balances as user1 balance is not called - check status unchanged
        refresh_balances(
            {
                "user_id": self.user.id,
                "channel_slug": self.bundle.bundle_id,
            }
        )
        self.assertTrue(mock_get_midas_response.called)

        user_pll_1.refresh_from_db()
        user_pll_2.refresh_from_db()
        self.assertEqual(user_pll_1.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)
        self.assertEqual(user_pll_2.state, WalletPLLStatus.INACTIVE.value)
        self.assertEqual(user_pll_2.slug, WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)

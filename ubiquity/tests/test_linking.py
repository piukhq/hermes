import json
import uuid
from copy import deepcopy
from unittest.mock import patch

from django.conf import settings
from django.test import override_settings, testcases
from factory.fuzzy import FuzzyAttribute
from rest_framework.reverse import reverse

from history.utils import GlobalMockAPITestCase
from payment_card.models import PaymentCardAccount
from payment_card.tests.factories import IssuerFactory, PaymentCardAccountFactory, PaymentCardFactory, fake
from scheme.models import SchemeAccount, SchemeBundleAssociation
from scheme.tests.factories import SchemeAccountFactory, SchemeBundleAssociationFactory, SchemeFactory
from ubiquity.models import (  # WalletPLLData,
    AccountLinkStatus,
    PaymentCardAccountEntry,
    PaymentCardSchemeEntry,
    PllUserAssociation,
    WalletPLLSlug,
    WalletPLLStatus,
)
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory
from ubiquity.tests.property_token import GenerateJWToken
from user.tests.factories import (
    ClientApplicationBundleFactory,
    ClientApplicationFactory,
    OrganisationFactory,
    UserFactory,
)


class RequestMock:
    channels_permit = None


class ChannelPermitMock:
    def __init__(self, client=None):
        self.client = client


class LinkAnalyst:
    def __init__(self, linked):
        self.count = len(linked)
        self.links_by_membership = {}
        self.links_by_payment = {}
        self.soft_links = []
        self.active_links = []
        for link in linked:
            scheme_account_id = link.scheme_account_id
            if not self.links_by_membership.get(scheme_account_id):
                self.links_by_membership[scheme_account_id] = [link]
            else:
                self.links_by_membership[scheme_account_id].append(link)
            payment_card_account_id = link.payment_card_account_id
            if not self.links_by_payment.get(payment_card_account_id):
                self.links_by_payment[payment_card_account_id] = [link]
            else:
                self.links_by_payment[payment_card_account_id].append(link)
            if link.active_link:
                self.active_links.append(link)
            else:
                self.soft_links.append(link)
        self.count_active_links = len(self.active_links)
        self.count_soft_links = len(self.soft_links)


def set_up_payment_card(
    name_on_card="test user 2",
    last_four=5234,
    token="H7FdKWKPOPhepzxS4MfUuvTDHxr",
    fingerprint="b5fe350d5135ab64a8f3c1097fadefd9effb",
):
    organisation = OrganisationFactory(name="test_organisation")
    client_app = ClientApplicationFactory(
        organisation=organisation,
        name="set up client application",
        client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi",
    )
    bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=client_app)

    issuer = IssuerFactory(name="Barclays")
    payment_card = PaymentCardFactory(slug="visa", system="visa")

    version_header = {"HTTP_ACCEPT": "Application/json;v=1.1"}

    payload = {
        "card": {
            "last_four_digits": last_four,
            "currency_code": "GBP",
            "first_six_digits": 423456,
            "name_on_card": name_on_card,
            "token": token,
            "fingerprint": fingerprint,
            "year": 22,
            "month": 3,
            "order": 1,
        },
        "account": {"consents": [{"timestamp": 1517549941, "type": 0}]},
    }
    return client_app, bundle, issuer, payment_card, version_header, payload


def set_up_scheme(bundle):
    scheme = SchemeFactory()
    scheme_bundle_association = SchemeBundleAssociationFactory(
        scheme=scheme, bundle=bundle, status=SchemeBundleAssociation.ACTIVE
    )
    return scheme, scheme_bundle_association


def set_up_membership_card(user, scheme, link_status=1):
    scheme_account = SchemeAccountFactory(scheme=scheme)
    scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account, user=user, link_status=link_status)
    return scheme_account, scheme_account_entry


def set_up_payment_card_account(payment_card, issuer, payload, status=PaymentCardAccount.ACTIVE):
    card = payload["card"]
    fingerprint = card.get("fingerprint", FuzzyAttribute(uuid.uuid4))
    name_on_card = card.get("name_on_card", fake.name())
    pan_end = card.get("last_four_digits", 5234)
    pan_start = card.get("first_six_digits", 423456)
    token = card.get("token", FuzzyAttribute(uuid.uuid4))
    currency_code = card.get("currency_code", "GBP")
    year = card.get("year", 22)
    month = card.get("month", 3)
    order = card.get("order", 1)
    return PaymentCardAccountFactory(
        payment_card=payment_card,
        fingerprint=fingerprint,
        issuer=issuer,
        name_on_card=name_on_card,
        pan_start=pan_start,
        pan_end=pan_end,
        token=token,
        status=status,
        start_year=year,
        start_month=month,
        expiry_year=year + 3,
        expiry_month=12,
        order=order,
        currency_code=currency_code,
    )


def add_payment_card_account_to_wallet(payment_card_account, user):
    return PaymentCardAccountEntry.objects.get_or_create(payment_card_account=payment_card_account, user=user)


class TestUserPLL(testcases.TestCase):
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

        # senario 1 mcards 1 cards 1 mplan

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

    @staticmethod
    def get_user_and_base_pll(payment_card_account, scheme_account, user):
        base_pll = PaymentCardSchemeEntry.objects.get(
            payment_card_account=payment_card_account, scheme_account=scheme_account
        )
        user_pll = PllUserAssociation.objects.get(pll=base_pll, user=user)
        return user_pll, base_pll

    @patch("ubiquity.models.PaymentCardSchemeEntry.vop_activate_check")
    def test_link_accounts_active_pay_to_active_scheme(self, activate_check):
        scheme_account, _ = set_up_membership_card(self.user_wallet_1, self.scheme1)
        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_1)
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, [self.payment_card_account_1], self.user_wallet_1
        )
        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )
        self.assertTrue(base_pll.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.ACTIVE)
        self.assertEqual(user_pll.slug, "")
        self.assertEqual(activate_check.call_count, 1)

    @patch("ubiquity.models.PaymentCardSchemeEntry.vop_activate_check")
    def test_link_accounts_active_pay_to_pending_scheme(self, activate_check):
        scheme_account, _ = set_up_membership_card(
            self.user_wallet_1, self.scheme1, link_status=AccountLinkStatus.PENDING
        )
        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_1)
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, [self.payment_card_account_1], self.user_wallet_1
        )
        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )
        self.assertFalse(base_pll.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.PENDING)
        self.assertEqual(user_pll.slug, WalletPLLSlug.LOYALTY_CARD_PENDING.value)
        self.assertEqual(activate_check.call_count, 0)

    def test_ppl_linking_duplicate_cards_in_2_wallets(self):
        """
        This tests the PllUserAssociation logic when duplicate payment and scheme accounts are
        linked in two wallets.
        Note a bug was reported which might imply this did not work correctly. This test proves
        the PllUserAssociation logic works in this scenario
        Error reported in LOY-2874
        expected result: wallet1 has PLL status = PAYMENT_ACCOUNT_PENDING  wallet2 = LOYALTY_CARD_NOT_AUTHORISED
        Steps to reproduce:
        1. In Wallet_1 add and auth iceland card.
        2. In Wallet_1 add Pending payment card with token ERRRET_500
        3. GET /wallet. PLL link shows PAYMENT_ACCOUNT_PENDING as expected.
        4. In Wallet_2 add Wallet_only card from step 1 (with only add credentials).
            Or add and auth the same iceland card from step 1(with add and auth credentials).
        5. Add the same pending card from step 2 in Wallet_2
        6. GET /wallet. PLL link shows LOYALTY_CARD_NOT_AUTHORISED as expected in the second wallet
        7. Call Get wallet_1 again. PLL in Wallet_1 is updated and
          now shows LOYALTY_CARD_NOT_AUTHORISED instead of PAYMENT_ACCOUNT_PENDING.
        """

        # 1 to 3 - check wallet 1 is set up - user pll expected as PAYMENT_ACCOUNT_PENDING

        shared_payment_card_account = set_up_payment_card_account(
            self.payment_card, issuer=self.issuer, payload=self.payload_1, status=PaymentCardAccount.PENDING
        )
        shared_scheme_account, _ = set_up_membership_card(
            self.user_wallet_1, self.scheme1, link_status=AccountLinkStatus.ACTIVE
        )

        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            payment_card_accounts=[shared_payment_card_account],
            scheme_account=shared_scheme_account,
            user=self.user_wallet_1,
        )
        PaymentCardAccountEntryFactory(user=self.user_wallet_1, payment_card_account=shared_payment_card_account)
        user_pll_1 = PllUserAssociation.objects.get(pll__scheme_account=shared_scheme_account, user=self.user_wallet_1)

        self.assertEqual(user_pll_1.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)

        # Step 4 add same scheme account to Wallet2
        scheme_account_entry_2 = SchemeAccountEntryFactory.create(
            scheme_account=shared_scheme_account, user=self.user_wallet_2
        )
        scheme_account_entry_2.link_status = AccountLinkStatus.WALLET_ONLY
        scheme_account_entry_2.save()

        # Step 5 add same payment card to Wallet2
        PaymentCardAccountEntryFactory(user=self.user_wallet_2, payment_card_account=shared_payment_card_account)

        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            payment_card_accounts=[shared_payment_card_account],
            scheme_account=shared_scheme_account,
            user=self.user_wallet_2,
        )
        user_pll_1.refresh_from_db()
        user_pll_2 = PllUserAssociation.objects.get(pll__scheme_account=shared_scheme_account, user=self.user_wallet_2)
        self.assertEqual(user_pll_1.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)
        self.assertEqual(user_pll_2.state, WalletPLLStatus.INACTIVE.value)
        self.assertEqual(user_pll_2.slug, WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)

        # Now check PLL update by payment account
        PllUserAssociation.update_user_pll_by_pay_account(payment_card_account=shared_payment_card_account)

        user_pll_1.refresh_from_db()
        user_pll_2.refresh_from_db()
        self.assertEqual(user_pll_1.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)
        self.assertEqual(user_pll_2.state, WalletPLLStatus.INACTIVE.value)
        self.assertEqual(user_pll_2.slug, WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)

        # Now check PLL update by scheme account
        PllUserAssociation.update_user_pll_by_scheme_account(scheme_account=shared_scheme_account)

        user_pll_1.refresh_from_db()
        user_pll_2.refresh_from_db()
        self.assertEqual(user_pll_1.state, WalletPLLStatus.PENDING.value)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)
        self.assertEqual(user_pll_2.state, WalletPLLStatus.INACTIVE.value)
        self.assertEqual(user_pll_2.slug, WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)

    @patch("ubiquity.models.PaymentCardSchemeEntry.vop_activate_check")
    def test_link_accounts_ubiquity_collision(self, activate_check):
        scheme_account_1, _ = set_up_membership_card(
            self.user_wallet_1, self.scheme1, link_status=AccountLinkStatus.ACTIVE
        )
        scheme_account_2, _ = set_up_membership_card(
            self.user_wallet_2, self.scheme1, link_status=AccountLinkStatus.ACTIVE
        )
        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_1)
        add_payment_card_account_to_wallet(self.payment_card_account_2, self.user_wallet_2)
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account_1, [self.payment_card_account_1], self.user_wallet_1
        )
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account_2, [self.payment_card_account_1], self.user_wallet_2
        )
        user_pll_1, base_pll_1 = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account_1, user=self.user_wallet_1
        )
        user_pll_2, base_pll_2 = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account_2, user=self.user_wallet_2
        )

        self.assertTrue(base_pll_1.active_link, "1st PLL before Collision must be True")
        self.assertFalse(base_pll_2.active_link, "PLL for Collided object must be False")
        self.assertEqual(user_pll_1.state, WalletPLLStatus.ACTIVE)
        self.assertEqual(user_pll_1.slug, "")
        self.assertEqual(user_pll_2.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_pll_2.slug, WalletPLLSlug.UBIQUITY_COLLISION.value)
        self.assertEqual(activate_check.call_count, 1, "Only one account should have been activated")

    @patch("ubiquity.models.PaymentCardSchemeEntry.vop_activate_check")
    def test_update_user_pll_by_scheme_account(self, activate_check):
        """
        1. Add a PllUserAssociation for a Pending Scheme account and active payment cards
        2. Check status then set Scheme account Active
        3. Check PllUserAssociation.update_user_pll_by_scheme_account() updates both user and base pll links are active
           and card activation is called
        """
        scheme_account, scheme_account_entry = set_up_membership_card(
            self.user_wallet_1, self.scheme1, link_status=AccountLinkStatus.PENDING
        )
        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_1)
        # Link the cards
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, [self.payment_card_account_1], self.user_wallet_1
        )
        self.assertEqual(activate_check.call_count, 0, "No PLL should be activated")
        user_pll_1, base_pll_1 = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )

        self.assertEqual(user_pll_1.state, WalletPLLStatus.PENDING)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.LOYALTY_CARD_PENDING.value)
        self.assertFalse(base_pll_1.active_link)
        # Now test update_user_pll_by_scheme_account if the scheme account goes active
        scheme_account_entry.link_status = AccountLinkStatus.ACTIVE
        scheme_account_entry.save()
        PllUserAssociation.update_user_pll_by_scheme_account(scheme_account)
        user_pll_1, base_pll_1 = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )
        self.assertEqual(user_pll_1.state, WalletPLLStatus.ACTIVE)
        self.assertEqual(user_pll_1.slug, "")
        self.assertTrue(base_pll_1.active_link)

        self.assertEqual(activate_check.call_count, 1, "PLL should be activated")

    @patch("ubiquity.models.PaymentCardSchemeEntry.vop_activate_check")
    def test_updating_base_link_when_link_status_changes(self, activate_check):
        scheme_account, scheme_account_entry = set_up_membership_card(self.user_wallet_1, self.scheme1)
        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_1)
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, [self.payment_card_account_1], self.user_wallet_1
        )
        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )
        self.assertTrue(base_pll.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.ACTIVE)
        self.assertEqual(user_pll.slug, "")
        self.assertEqual(activate_check.call_count, 1)

        scheme_account_entry.set_link_status(AccountLinkStatus.INVALID_CREDENTIALS)

        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )

        # Check base link has been update when SchemeAccountEntry link_status has changed
        self.assertFalse(base_pll.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_pll.slug, WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)

    @patch("ubiquity.models.PaymentCardSchemeEntry.vop_activate_check")
    def test_updating_base_link_when_link_status_changes_multi_wallet(self, activate_check):
        scheme_account, scheme_account_entry = set_up_membership_card(self.user_wallet_1, self.scheme1)
        scheme_account_entry_2 = SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user_wallet_2)

        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_1)
        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_2)

        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, [self.payment_card_account_1], self.user_wallet_1
        )
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, [self.payment_card_account_1], self.user_wallet_2
        )
        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )
        user_pll2, base_pll2 = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_2
        )

        self.assertTrue(base_pll.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.ACTIVE)
        self.assertEqual(user_pll.slug, "")
        self.assertEqual(activate_check.call_count, 1)
        self.assertTrue(base_pll2.active_link)
        self.assertEqual(user_pll2.state, WalletPLLStatus.ACTIVE)
        self.assertEqual(user_pll2.slug, "")

        scheme_account_entry.set_link_status(AccountLinkStatus.INVALID_CREDENTIALS)

        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )

        # base link remains active
        self.assertTrue(base_pll.active_link)

        scheme_account_entry_2.set_link_status(AccountLinkStatus.INVALID_CREDENTIALS)

        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )

        # Both now not active so base link should be False
        self.assertFalse(base_pll.active_link)

    @patch("ubiquity.models.PaymentCardSchemeEntry.vop_activate_check")
    def test_updating_base_link_when_pcard_status_changes(self, activate_check):
        scheme_account, scheme_account_entry = set_up_membership_card(self.user_wallet_1, self.scheme1)
        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_1)
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, [self.payment_card_account_1], self.user_wallet_1
        )
        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )
        self.assertTrue(base_pll.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.ACTIVE)
        self.assertEqual(user_pll.slug, "")
        self.assertEqual(activate_check.call_count, 1)

        base_pll.payment_card_account.status = PaymentCardAccount.INVALID_CARD_DETAILS
        base_pll.payment_card_account.save(update_fields=["status"])

        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )

        # Check base link has changed when payment card status has changed.
        self.assertFalse(base_pll.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_pll.slug, WalletPLLSlug.PAYMENT_ACCOUNT_INACTIVE.value)

    @patch("ubiquity.models.PaymentCardSchemeEntry.vop_activate_check")
    def test_active_base_pll_multi_wallet_is_not_updated(self, activate_check):
        """
        This test a multi wallet scenario where the base link is already active and adding the same loyalty card but
        with a link_status of INVALID_CREDENTIALS and payment card to another wallet does not change the base link.
        """

        scheme_account, scheme_account_entry = set_up_membership_card(self.user_wallet_1, self.scheme1)
        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_1)
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, [self.payment_card_account_1], self.user_wallet_1
        )
        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )

        self.assertTrue(base_pll.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.ACTIVE)
        self.assertEqual(user_pll.slug, "")
        self.assertEqual(activate_check.call_count, 1)

        # Second Wallet with invalid loyalty card
        SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=self.user_wallet_2, link_status=AccountLinkStatus.INVALID_CREDENTIALS
        )
        # Add same payment card to wallet 2
        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_2)
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, [self.payment_card_account_1], self.user_wallet_2
        )

        # Get user pll associations
        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )
        user_pll_2, base_pll_2 = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_2
        )

        # base link should still be active even though wallet 2 has an inactive loyalty card
        self.assertTrue(base_pll.active_link)
        self.assertTrue(base_pll_2.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.ACTIVE)
        self.assertEqual(user_pll_2.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_pll.slug, "")
        self.assertEqual(user_pll_2.slug, WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)

    @patch("ubiquity.models.PaymentCardSchemeEntry.vop_activate_check")
    def test_user_pll_changes_after_base_link_goes_active(self, activate_check):
        """
        This test a multi wallet scenario where the base link is already active and adding the same loyalty card but
        with a link_status of INVALID_CREDENTIALS and payment card to another wallet does not change the base link.
        """
        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_1)
        scheme_account, scheme_account_entry = set_up_membership_card(
            self.user_wallet_1, self.scheme1, link_status=AccountLinkStatus.INVALID_CREDENTIALS
        )
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, [self.payment_card_account_1], self.user_wallet_1
        )
        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )

        self.assertFalse(base_pll.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_pll.slug, WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)

        # Second wallet
        add_payment_card_account_to_wallet(self.payment_card_account_1, self.user_wallet_2)
        scheme_account_2 = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=self.user_wallet_2, link_status=AccountLinkStatus.ADD_AUTH_PENDING
        )
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, [self.payment_card_account_1], self.user_wallet_2
        )
        # Active loyalty card after add_auth
        scheme_account_2.set_link_status(AccountLinkStatus.ACTIVE)

        # Get user pll associations
        user_pll, base_pll = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_1
        )
        user_pll_2, base_pll_2 = self.get_user_and_base_pll(
            payment_card_account=self.payment_card_account_1, scheme_account=scheme_account, user=self.user_wallet_2
        )

        # base link should still be active even though wallet 2 has an inactive loyalty card
        self.assertTrue(base_pll.active_link)
        self.assertTrue(base_pll_2.active_link)
        self.assertEqual(user_pll.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_pll_2.state, WalletPLLStatus.ACTIVE)
        self.assertEqual(user_pll.slug, WalletPLLSlug.LOYALTY_CARD_NOT_AUTHORISED.value)
        self.assertEqual(user_pll_2.slug, "")
        self.assertEqual(activate_check.call_count, 1)


class TestSoftLinking(GlobalMockAPITestCase):
    def _get_auth_token(self, user):
        token = GenerateJWToken(
            self.client_app.organisation.name, self.client_app.secret, self.bundle.bundle_id, user.external_id
        ).get_token()
        return "Bearer {}".format(token)

    def _get_auth_headers(self, user):
        return {"HTTP_AUTHORIZATION": f"{self._get_auth_token(user)}"}

    def _get_service_auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Token {settings.SERVICE_API_KEY}"}

    @staticmethod
    def failed_midas_callback(request, uri, response_headers):
        return [SchemeAccount.AGENT_NOT_FOUND, response_headers, ""]

    def auto_link_post(self, payload, user):
        resp = self.client.post(
            f'{reverse("payment-cards")}?autoLink=True',
            data=json.dumps(payload),
            content_type="application/json",
            **self._get_auth_headers(user),
            **self.version_header,
        )
        linked_info = LinkAnalyst(PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data["id"]))
        return resp, linked_info

    def metis_callback(self, card_id=None, status_code=PaymentCardAccount.ACTIVE):
        payload = {
            "status": status_code,
            "id": card_id,
        }
        resp = self.client.put(
            f'{reverse("update_payment_card_account_status")}',
            data=json.dumps(payload),
            content_type="application/json",
            **self._get_service_auth_headers(),
        )
        linked_info = LinkAnalyst(PaymentCardSchemeEntry.objects.filter(payment_card_account_id=card_id))
        return resp, linked_info

    @classmethod
    def setUpTestData(cls):
        (
            cls.client_app,
            cls.bundle,
            cls.issuer,
            cls.payment_card,
            cls.version_header,
            cls.payload,
        ) = set_up_payment_card()
        external_id = "test@user.com"
        cls.user = UserFactory(external_id=external_id, client=cls.client_app, email=external_id)
        cls.scheme1, cls.scheme_bundle_association1 = set_up_scheme(cls.bundle)
        cls.scheme_account_c1_s1, _ = set_up_membership_card(cls.user, cls.scheme1)

        cls.scheme2, cls.scheme_bundle_association2 = set_up_scheme(cls.bundle)
        cls.scheme_account_c2_s2, _ = set_up_membership_card(cls.user, cls.scheme2)

        cls.scheme3, cls.scheme_bundle_association3 = set_up_scheme(cls.bundle)
        cls.scheme_account_c3_s3, _ = set_up_membership_card(cls.user, cls.scheme3)

    """
    This test needs refactor to new VOP spec
    @httpretty.activate
    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    @patch('payment_card.views.vop_activate')
    @patch('hermes.vop_tasks.vop_activate')
    def test_active_membership_linking_to_payment_card(self, *_):
        # set mcard 2 to pending
        self.scheme_account_c2_s2.status = SchemeAccount.REGISTRATION_FAILED
        self.scheme_account_c2_s2.save()
        resp, linked = self.auto_link_post(self.payload, self.user)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 0)
        # Confirm 3 soft linked cards since payment card is pending
        self.assertEqual(linked.count, 3)
        self.assertEqual(linked.count_soft_links, 3)
        # Now make fail Payment Card with Metis Callback and check none go active
        payment_card_id = resp.data['id']
        resp, linked = self.metis_callback(payment_card_id, status_code=PaymentCardAccount.INVALID_CARD_DETAILS)
        self.assertEqual(linked.count, 3)
        self.assertEqual(linked.count_soft_links, 3)
        # Now make activate Payment Card with Metis Callback
        resp, linked = self.metis_callback(payment_card_id)
        self.assertEqual(resp.status_code, 200)
        # Only 2 active cards should link - soft linked should be self.scheme_account_c2_s2
        self.assertEqual(linked.count_soft_links, 1)
        self.assertEqual(linked.count_active_links, 2)
        self.assertEqual(linked.soft_links[0].scheme_account_id, self.scheme_account_c2_s2.id)
        # todo could add get membership cards and payment cards call here to check status via API
        # Now see if a get balance will activate link
        uri = f'{settings.MIDAS_URL}/{self.scheme2.slug}/balance'
        httpretty.register_uri(
            httpretty.GET,
            uri,
            body=json.dumps({
                "balance": 5
            })
        )
        self.scheme_account_c2_s2.get_balance(JourneyTypes.UPDATE)
        linked = LinkAnalyst(PaymentCardSchemeEntry.objects.filter(payment_card_account_id=payment_card_id))
        self.assertEqual(linked.count_soft_links, 0)
        self.assertEqual(linked.count_active_links, 3)
        # Now see if a get balance fail will convert back to softlink
        httpretty.register_uri(
            httpretty.GET,
            uri,
            body=self.failed_midas_callback
        )
        self.scheme_account_c2_s2.get_balance(JourneyTypes.UPDATE)
        linked = LinkAnalyst(PaymentCardSchemeEntry.objects.filter(payment_card_account_id=payment_card_id))
        self.assertEqual(linked.count_soft_links, 1)
        self.assertEqual(linked.count_active_links, 2)
        self.assertEqual(linked.soft_links[0].scheme_account_id, self.scheme_account_c2_s2.id)
    """


class TestPaymentAutoLink(GlobalMockAPITestCase):
    def _get_auth_token(self, user):
        token = GenerateJWToken(
            self.client_app.organisation.name, self.client_app.secret, self.bundle.bundle_id, user.external_id
        ).get_token()
        return "Bearer {}".format(token)

    def _get_auth_headers(self, user):
        return {"HTTP_AUTHORIZATION": f"{self._get_auth_token(user)}"}

    @classmethod
    def setUpTestData(cls):
        (
            cls.client_app,
            cls.bundle,
            cls.issuer,
            cls.payment_card,
            cls.version_header,
            cls.payload,
        ) = set_up_payment_card()
        cls.payload2 = {
            "card": {
                "last_four_digits": 5288,
                "currency_code": "GBP",
                "first_six_digits": 423456,
                "name_on_card": "test user 3",
                "token": "H7FdKWKPOPhepzxS4MfUuvABCDe",
                "fingerprint": "b5fe350d5135ab64a8f3c1097fadefdabcde",
                "year": 23,
                "month": 1,
                "order": 2,
            },
            "account": {"consents": [{"timestamp": 1517549941, "type": 0}]},
        }

        # senario 1 mcards 1 cards 1 mplan

        external_id1 = "test@user.com"
        cls.user1 = UserFactory(external_id=external_id1, client=cls.client_app, email=external_id1)

        cls.scheme1 = SchemeFactory()
        cls.scheme_account_c1_p1 = SchemeAccountFactory(scheme=cls.scheme1)
        cls.scheme_account_entry1 = SchemeAccountEntryFactory(scheme_account=cls.scheme_account_c1_p1, user=cls.user1)
        cls.scheme_bundle_association_p1 = SchemeBundleAssociationFactory(
            scheme=cls.scheme1, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        # senario 2 mcards 2 cards different mplan

        external_id2 = "test2@user.com"
        cls.user2 = UserFactory(external_id=external_id2, client=cls.client_app, email=external_id2)
        cls.scheme2 = SchemeFactory()
        cls.scheme_account_c1_p2 = SchemeAccountFactory(scheme=cls.scheme2)
        cls.scheme_account_entry2 = SchemeAccountEntryFactory(scheme_account=cls.scheme_account_c1_p2, user=cls.user2)
        cls.scheme_bundle_association_p2 = SchemeBundleAssociationFactory(
            scheme=cls.scheme2, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        cls.scheme3 = SchemeFactory()
        cls.scheme_bundle_association_p3 = SchemeBundleAssociationFactory(
            scheme=cls.scheme3, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )
        cls.scheme_account_c2_p3 = SchemeAccountFactory(scheme=cls.scheme3)
        cls.scheme_account_entry3 = SchemeAccountEntryFactory(scheme_account=cls.scheme_account_c2_p3, user=cls.user2)

        # senario 3 mcards of same mplan

        external_id3 = "test3@user.com"
        cls.user3 = UserFactory(external_id=external_id3, client=cls.client_app, email=external_id3)
        cls.scheme4 = SchemeFactory()
        cls.scheme_bundle_association_p4 = SchemeBundleAssociationFactory(
            scheme=cls.scheme4, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )
        cls.scheme_account_c1_p4 = SchemeAccountFactory(scheme=cls.scheme4)
        cls.scheme_account_entry4 = SchemeAccountEntryFactory(scheme_account=cls.scheme_account_c1_p4, user=cls.user3)
        cls.scheme_account_c2_p4 = SchemeAccountFactory(scheme=cls.scheme4)
        cls.scheme_account_entry4 = SchemeAccountEntryFactory(scheme_account=cls.scheme_account_c2_p4, user=cls.user3)
        cls.scheme_account_c3_p4 = SchemeAccountFactory(scheme=cls.scheme4)
        cls.scheme_account_entry4 = SchemeAccountEntryFactory(scheme_account=cls.scheme_account_c3_p4, user=cls.user3)
        cls.scheme_account_c4_p4 = SchemeAccountFactory(scheme=cls.scheme4)
        cls.scheme_account_entry4 = SchemeAccountEntryFactory(scheme_account=cls.scheme_account_c4_p4, user=cls.user3)

        # senario 4 2 users 4 mcards of same mplan

        external_id4 = "test4@user.com"
        external_id5 = "test5@user.com"
        cls.user4 = UserFactory(external_id=external_id4, client=cls.client_app, email=external_id4)
        cls.user5 = UserFactory(external_id=external_id5, client=cls.client_app, email=external_id5)
        cls.scheme5 = SchemeFactory()
        cls.scheme_bundle_association_p4 = SchemeBundleAssociationFactory(
            scheme=cls.scheme5, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        cls.scheme_account_c1_p5_u4 = SchemeAccountFactory(scheme=cls.scheme5)
        cls.scheme_account_entry_c1_p5_u4 = SchemeAccountEntryFactory(
            scheme_account=cls.scheme_account_c1_p5_u4, user=cls.user4
        )
        cls.scheme_account_c2_p5_u4 = SchemeAccountFactory(scheme=cls.scheme5)
        cls.scheme_account_entry_c2_p5_u4 = SchemeAccountEntryFactory(
            scheme_account=cls.scheme_account_c2_p5_u4, user=cls.user4
        )
        # user 5 has  2 scheme accounts with the same scheme (no. 5) linked to a payment card no. 5
        cls.scheme_account_c3_p5_u5 = SchemeAccountFactory(scheme=cls.scheme5)
        cls.scheme_account_entry_c3_p5_u5 = SchemeAccountEntryFactory(
            scheme_account=cls.scheme_account_c3_p5_u5, user=cls.user5
        )
        cls.scheme_account_c4_p5_u5 = SchemeAccountFactory(scheme=cls.scheme5)
        cls.scheme_account_entry_c4_p5_u5 = SchemeAccountEntryFactory(
            scheme_account=cls.scheme_account_c4_p5_u5, user=cls.user5
        )

    def auto_link_post(self, payload, user, query_string="?autoLink=True"):
        resp = self.client.post(
            f'{reverse("payment-cards")}{query_string}',
            data=json.dumps(payload),
            content_type="application/json",
            **self._get_auth_headers(user),
            **self.version_header,
        )
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data["id"])
        return resp, linked

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_creation_auto_link(self, *_):
        # scenario 1 1 membership cards 1 plans - user 1
        resp, linked = self.auto_link_post(self.payload, self.user1)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["membership_cards"]), 0)
        self.assertEqual(len(linked), 1)

        # Repeat auto link to ensure nothing extra is added and 200 returned
        resp, linked = self.auto_link_post(self.payload, self.user1)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["membership_cards"]), 0)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data["id"])
        self.assertEqual(len(linked), 1)

        # Add another membership card
        scheme2 = SchemeFactory()
        SchemeBundleAssociationFactory(scheme=scheme2, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE)
        scheme_account2 = SchemeAccountFactory(scheme=scheme2)
        SchemeAccountEntryFactory(scheme_account=scheme_account2, user=self.user1)

        # Try to add again and see if auto links
        resp, linked = self.auto_link_post(self.payload, self.user1)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["membership_cards"]), 0)
        self.assertEqual(len(linked), 2)

        # Make the links active
        for link in linked:
            link.active_link = True
            link.save()

        # Try to add again and see if auto links = True
        resp, linked = self.auto_link_post(self.payload, self.user1)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["membership_cards"]), 2)
        self.assertEqual(len(linked), 2)
        for item in resp.data["membership_cards"]:
            self.assertEqual(item["active_link"], True)
            self.assertIn("id", item)
            self.assertEqual(len(item), 2)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_auto_link_2_cards_different_plans(self, *_):
        # senario 2 2 membership cards 2 plans - user 2
        resp, linked = self.auto_link_post(self.payload, self.user2)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["membership_cards"]), 0)
        self.assertEqual(len(linked), 2)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_auto_link_4_cards_same_plan(self, *_):
        # senario 3 4 membership cards 1 plans - user 3
        resp, linked = self.auto_link_post(self.payload, self.user3)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["membership_cards"]), 0)
        # The payment card with lowest id is Pending the other collided
        self.assertEqual(len(linked), 4)
        user_pll_0 = PllUserAssociation.objects.get(pll=linked[0], user=self.user3)
        user_pll_1 = PllUserAssociation.objects.get(pll=linked[1], user=self.user3)
        user_pll_2 = PllUserAssociation.objects.get(pll=linked[2], user=self.user3)
        user_pll_3 = PllUserAssociation.objects.get(pll=linked[3], user=self.user3)
        self.assertEqual(user_pll_0.state, WalletPLLStatus.PENDING)
        self.assertEqual(user_pll_0.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)
        self.assertEqual(user_pll_1.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.UBIQUITY_COLLISION.value)
        self.assertEqual(user_pll_2.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_pll_2.slug, WalletPLLSlug.UBIQUITY_COLLISION.value)
        self.assertEqual(user_pll_3.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_pll_3.slug, WalletPLLSlug.UBIQUITY_COLLISION.value)
        self.assertFalse(linked[0].active_link)
        self.assertFalse(linked[1].active_link)
        self.assertFalse(linked[1].active_link)
        self.assertFalse(linked[1].active_link)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c1_p4.id)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_auto_link_2cards_1users_same_plan(self, *_):
        # senario 4 4 membership cards 1 plans - user 4
        resp, linked = self.auto_link_post(self.payload, self.user4)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["membership_cards"]), 0)
        # The payment card with lowest id is Pending the other collided
        self.assertEqual(len(linked), 2)
        self.assertFalse(linked[0].active_link)
        self.assertFalse(linked[1].active_link)
        user_pll_0 = PllUserAssociation.objects.get(pll=linked[0], user=self.user4)
        user_pll_1 = PllUserAssociation.objects.get(pll=linked[1], user=self.user4)
        self.assertEqual(user_pll_0.state, WalletPLLStatus.PENDING)
        self.assertEqual(user_pll_0.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)
        self.assertEqual(user_pll_1.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_pll_1.slug, WalletPLLSlug.UBIQUITY_COLLISION.value)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c1_p5_u4.id)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_auto_link_4cards_2users_same_plan_other_user_linked(self, *_):
        # senario 4 4 membership cards 1 plans - user 5
        # now with user 5 instead of 4 auto link
        resp, linked = self.auto_link_post(self.payload, self.user5)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["membership_cards"]), 0)
        # Test only card linked to payment card has lowest id in users wallet
        self.assertEqual(len(linked), 2)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)

        # now repeat user 4 auto link
        resp, linked = self.auto_link_post(self.payload, self.user4)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["membership_cards"]), 0)

        # Only first should be pending even though not the oldest, the rest are collision and inactive
        self.assertEqual(len(linked), 4)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)
        self.assertFalse(linked[0].active_link)
        self.assertFalse(linked[1].active_link)
        self.assertFalse(linked[2].active_link)
        self.assertFalse(linked[3].active_link)
        self.assertEqual(linked[0].payment_card_account.fingerprint, self.payload["card"]["fingerprint"])
        self.assertEqual(linked[1].payment_card_account.fingerprint, self.payload["card"]["fingerprint"])
        self.assertEqual(linked[2].payment_card_account.fingerprint, self.payload["card"]["fingerprint"])
        self.assertEqual(linked[3].payment_card_account.fingerprint, self.payload["card"]["fingerprint"])
        user_plls_u5_0 = PllUserAssociation.objects.get(pll=linked[0], user=self.user5)
        user_plls_u5_1 = PllUserAssociation.objects.get(pll=linked[1], user=self.user5)
        user_plls_u4 = PllUserAssociation.objects.filter(user=self.user4).all()
        self.assertEqual(len(user_plls_u4), 2)
        self.assertEqual(user_plls_u5_0.state, WalletPLLStatus.PENDING)
        self.assertEqual(user_plls_u5_0.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)
        self.assertEqual(user_plls_u5_1.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_plls_u5_1.slug, WalletPLLSlug.UBIQUITY_COLLISION.value)
        self.assertEqual(user_plls_u4[0].state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_plls_u4[0].slug, WalletPLLSlug.UBIQUITY_COLLISION.value)
        self.assertEqual(user_plls_u4[1].state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_plls_u4[1].slug, WalletPLLSlug.UBIQUITY_COLLISION.value)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_auto_link_2_payment_cards(self, *_):
        # senario 4 4 membership cards 1 plans - user 5 but with an additional linked payment
        # now with user 5 instead of 4 auto link but with payment card 2
        resp, linked = self.auto_link_post(self.payload2, self.user5)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["membership_cards"]), 0)
        # Test two cards linked to payment card but the lowest id is pending highest is Ubiquity collided and inactive
        self.assertEqual(len(linked), 2)
        user_pll_0_p2 = PllUserAssociation.objects.get(pll=linked[0], user=self.user5)
        user_pll_1_p2 = PllUserAssociation.objects.get(pll=linked[1], user=self.user5)
        self.assertEqual(user_pll_0_p2.state, WalletPLLStatus.PENDING)
        self.assertEqual(user_pll_0_p2.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)
        self.assertEqual(user_pll_1_p2.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_pll_1_p2.slug, WalletPLLSlug.UBIQUITY_COLLISION.value)
        self.assertFalse(linked[0].active_link)
        self.assertFalse(linked[1].active_link)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)
        self.assertEqual(linked[0].payment_card_account.fingerprint, self.payload2["card"]["fingerprint"])
        self.assertEqual(linked[1].payment_card_account.fingerprint, self.payload2["card"]["fingerprint"])
        # now with user 5 instead of 4 auto link as previous test same result as before the auto linking of
        # another payment card should have no effect.

        resp2, linked2 = self.auto_link_post(self.payload, self.user5)
        self.assertEqual(resp2.status_code, 201)
        self.assertEqual(len(resp2.data["membership_cards"]), 0)
        # Test only card linked to payment card has lowest id in users wallet
        self.assertEqual(len(linked2), 2)
        user_pll_0_p1 = PllUserAssociation.objects.get(pll=linked2[0], user=self.user5)
        user_pll_1_p1 = PllUserAssociation.objects.get(pll=linked2[1], user=self.user5)
        self.assertEqual(user_pll_0_p1.state, WalletPLLStatus.PENDING)
        self.assertEqual(user_pll_0_p1.slug, WalletPLLSlug.PAYMENT_ACCOUNT_PENDING.value)
        self.assertEqual(user_pll_1_p1.state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_pll_1_p1.slug, WalletPLLSlug.UBIQUITY_COLLISION.value)
        self.assertFalse(linked2[0].active_link)
        self.assertFalse(linked2[1].active_link)
        self.assertEqual(linked2[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)
        self.assertEqual(linked2[0].payment_card_account.fingerprint, self.payload["card"]["fingerprint"])
        self.assertEqual(linked2[1].payment_card_account.fingerprint, self.payload["card"]["fingerprint"])

        # now repeat user 4 auto link with payload card which will then have 4 links
        resp3, linked3 = self.auto_link_post(self.payload, self.user4)
        self.assertEqual(resp3.status_code, 201)
        self.assertEqual(len(resp3.data["membership_cards"]), 0)

        # Now the list should have the card linked in plan above (the other users plan) even though not the oldest
        # Test uncollided card linked to payment card is the card already linked
        self.assertEqual(len(linked3), 4)
        self.assertFalse(linked3[0].active_link)
        self.assertFalse(linked3[1].active_link)
        self.assertFalse(linked3[2].active_link)
        self.assertFalse(linked3[3].active_link)
        self.assertEqual(linked3[0].payment_card_account.fingerprint, self.payload["card"]["fingerprint"])
        self.assertEqual(linked3[1].payment_card_account.fingerprint, self.payload["card"]["fingerprint"])
        self.assertEqual(linked3[2].payment_card_account.fingerprint, self.payload["card"]["fingerprint"])
        self.assertEqual(linked3[3].payment_card_account.fingerprint, self.payload["card"]["fingerprint"])

        # user 4 should have 2 new user links but as payment card was linked before all should be Ubiquity collision

        user_plls = PllUserAssociation.objects.filter(user=self.user4).all()
        self.assertEqual(len(user_plls), 2)
        self.assertEqual(user_plls[0].state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_plls[0].slug, WalletPLLSlug.UBIQUITY_COLLISION.value)
        self.assertEqual(user_plls[1].state, WalletPLLStatus.INACTIVE)
        self.assertEqual(user_plls[1].slug, WalletPLLSlug.UBIQUITY_COLLISION.value)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_auto_links_with_no_auto_link_param(self, *_):
        email = "testnoautolinkparam@bink.com"
        test_user = UserFactory(external_id=email, client=self.client_app, email=email)
        test_scheme_account_1 = SchemeAccountFactory(scheme=self.scheme1)
        test_scheme_account_2 = SchemeAccountFactory(scheme=self.scheme2)
        SchemeAccountEntryFactory(scheme_account=test_scheme_account_1, user=test_user)
        SchemeAccountEntryFactory(scheme_account=test_scheme_account_2, user=test_user)

        resp, linked = self.auto_link_post(self.payload, test_user, query_string="")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["membership_cards"]), 0)
        self.assertEqual(len(linked), 2)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_auto_link_set_as_false(self, *_):
        email = "testfalseautolinkparam@bink.com"
        test_user = UserFactory(external_id=email, client=self.client_app, email=email)
        test_scheme_account_1 = SchemeAccountFactory(scheme=self.scheme1)
        test_scheme_account_2 = SchemeAccountFactory(scheme=self.scheme2)
        SchemeAccountEntryFactory(scheme_account=test_scheme_account_1, user=test_user)
        SchemeAccountEntryFactory(scheme_account=test_scheme_account_2, user=test_user)

        resp, linked = self.auto_link_post(self.payload, test_user, query_string="?autoLink=False")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["membership_cards"]), 0)
        self.assertEqual(len(linked), 0)

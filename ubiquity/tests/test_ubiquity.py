import datetime
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import httpretty
from django.conf import settings
from django.test import RequestFactory, override_settings
from olympus_messaging import JoinApplication
from rest_framework.reverse import reverse
from shared_config_storage.credentials.encryption import BLAKE2sHash, RSACipher
from shared_config_storage.credentials.utils import AnswerTypeChoices

from history.utils import GlobalMockAPITestCase
from payment_card.models import PaymentCardAccount
from payment_card.tests.factories import IssuerFactory, PaymentCardAccountFactory, PaymentCardFactory
from scheme.credentials import (
    BARCODE,
    CARD_NUMBER,
    EMAIL,
    LAST_NAME,
    MERCHANT_IDENTIFIER,
    PASSWORD,
    PAYMENT_CARD_HASH,
    POSTCODE,
    USER_NAME,
)
from scheme.encryption import AESCipher
from scheme.mixins import BaseLinkMixin
from scheme.models import (
    JourneyTypes,
    SchemeAccount,
    SchemeAccountCredentialAnswer,
    SchemeBundleAssociation,
    SchemeCredentialQuestion,
    SchemeOverrideError,
    ThirdPartyConsentLink,
)
from scheme.tests.factories import (
    ConsentFactory,
    SchemeAccountFactory,
    SchemeBalanceDetailsFactory,
    SchemeBundleAssociationFactory,
    SchemeCredentialAnswerFactory,
    SchemeCredentialQuestionFactory,
    SchemeFactory,
    fake,
)
from ubiquity.censor_empty_fields import remove_empty
from ubiquity.channel_vault import AESKeyNames
from ubiquity.models import (
    AccountLinkStatus,
    PaymentCardAccountEntry,
    PaymentCardSchemeEntry,
    PllUserAssociation,
    SchemeAccountEntry,
    WalletPLLSlug,
    WalletPLLStatus,
)
from ubiquity.reason_codes import CURRENT_STATUS_CODES
from ubiquity.tasks import deleted_membership_card_cleanup
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory, ServiceConsentFactory
from ubiquity.tests.property_token import GenerateJWToken
from ubiquity.tests.test_serializers import mock_secrets
from ubiquity.versioning.base.serializers import MembershipCardSerializer as MembershipCardSerializer_base
from ubiquity.versioning.base.serializers import MembershipTransactionsMixin
from ubiquity.versioning.v1_2.serializers import (
    MembershipCardSerializer,
    MembershipPlanSerializer,
    PaymentCardSerializer,
)
from ubiquity.versioning.v1_3.serializers import MembershipCardSerializer as MembershipCardSerializer_V1_3
from ubiquity.views import MembershipCardView, detect_and_handle_escaped_unicode
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


class MockApiCache:
    key = None
    expire = None
    available_called = None

    def __init__(self, key, expire):
        MockApiCache.key = key
        MockApiCache.data = None
        MockApiCache.expire = expire
        MockApiCache.available_called = False
        MockApiCache.start_time = 0
        MockApiCache.subject = ""
        MockApiCache.cache_hi = 0
        MockApiCache.cache_lo = 0

    @property
    def available(self):
        MockApiCache.available_called = True
        return False

    @staticmethod
    def time_it_log(start_time, subject, high=200, low=50):
        MockApiCache.start_time = start_time
        MockApiCache.subject = subject
        MockApiCache.cache_hi = high
        MockApiCache.cache_lo = low
        return

    def save(self, data):
        MockApiCache.data = data


class TestResources(GlobalMockAPITestCase):
    @classmethod
    def _get_auth_header(cls, user):
        token = GenerateJWToken(
            cls.client_app.organisation.name, cls.client_app.secret, cls.bundle.bundle_id, user.external_id
        ).get_token()
        return "Bearer {}".format(token)

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

        cls.scheme.manual_question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme, type=BARCODE, label=BARCODE, manual_question=True, add_field=True, enrol_field=True
        )
        cls.secondary_question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme,
            type=LAST_NAME,
            label=LAST_NAME,
            third_party_identifier=True,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            auth_field=True,
            enrol_field=True,
            register_field=True,
        )
        cls.jwp_question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme,
            type=PAYMENT_CARD_HASH,
            label=PAYMENT_CARD_HASH,
            enrol_field=True,
            options=SchemeCredentialQuestion.OPTIONAL_JOIN,
        )

        # Need to add an active association since it was assumed no setting was enabled
        cls.scheme_bundle_association = SchemeBundleAssociationFactory(
            scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        cls.issuer = IssuerFactory(name="Barclays")
        cls.payment_card = PaymentCardFactory(slug="visa", system="visa")
        cls.pcard_hash1 = "some_hash"
        cls.pcard_hash2 = "5ae741975b4db7bc80072fe8f88f233ef4a67e1e1d7e3bbf68a314dfc6691636"

        cls.auth_headers = {"HTTP_AUTHORIZATION": "{}".format(cls._get_auth_header(cls.user))}
        cls.auth_headers_user2 = {"HTTP_AUTHORIZATION": "{}".format(cls._get_auth_header(cls.user2))}
        cls.version_header = {"HTTP_ACCEPT": "Application/json;v=1.1"}
        cls.version_header_v1_2 = {"HTTP_ACCEPT": "Application/json;v=1.2"}
        cls.version_header_v1_3 = {"HTTP_ACCEPT": "Application/json;v=1.3"}

        cls.put_scheme = SchemeFactory()
        SchemeBalanceDetailsFactory(scheme_id=cls.put_scheme)

        cls.scheme_bundle_association_put = SchemeBundleAssociationFactory(
            scheme=cls.put_scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )
        cls.put_scheme_manual_q = SchemeCredentialQuestionFactory(
            scheme=cls.put_scheme,
            type=CARD_NUMBER,
            label=CARD_NUMBER,
            manual_question=True,
            add_field=True,
        )
        cls.put_scheme_scan_q = SchemeCredentialQuestionFactory(
            scheme=cls.put_scheme,
            type=BARCODE,
            label=BARCODE,
            scan_question=True,
            add_field=True,
        )
        cls.put_scheme_auth_q = SchemeCredentialQuestionFactory(
            scheme=cls.put_scheme, type=PASSWORD, label=PASSWORD, auth_field=True
        )

        cls.wallet_only_scheme = SchemeFactory()
        cls.wallet_only_question = SchemeCredentialQuestionFactory(
            type=CARD_NUMBER,
            scheme=cls.wallet_only_scheme,
            manual_question=True,
            add_field=True,
        )
        cls.scheme_bundle_association_put = SchemeBundleAssociationFactory(
            scheme=cls.wallet_only_scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

    def setUp(self) -> None:
        self.payment_card_account = PaymentCardAccountFactory(
            issuer=self.issuer, payment_card=self.payment_card, hash=self.pcard_hash2
        )
        self.payment_card_account_entry = PaymentCardAccountEntryFactory(
            user=self.user, payment_card_account=self.payment_card_account
        )

        self.scheme_account = SchemeAccountFactory(scheme=self.scheme)

        self.scheme_account_entry = SchemeAccountEntryFactory.create(scheme_account=self.scheme_account, user=self.user)

        self.scheme_account_answer = SchemeCredentialAnswerFactory(
            question=self.scheme.manual_question,
            answer=fake.first_name().lower(),
            scheme_account_entry=self.scheme_account_entry,
        )
        self.second_scheme_account_answer = SchemeCredentialAnswerFactory(
            question=self.secondary_question,
            scheme_account_entry=self.scheme_account_entry,
        )
        self.second_scheme_account_answer.answer = AESCipher(AESKeyNames.LOCAL_AES_KEY).decrypt(
            self.second_scheme_account_answer.answer
        )

        self.scheme_account_entry.update_scheme_account_key_credential_fields()

        self.test_hades_transactions = [
            {
                "id": 1,
                "scheme_account_id": self.scheme_account.id,
                "created": "2020-05-19 14:36:35+00:00",
                "date": "2020-05-19 14:36:35+00:00",
                "description": "Test Transaction",
                "location": "Bink",
                "points": 200,
                "value": "A lot",
                "hash": "ewfnwoenfwen",
            }
        ]

    def _setup_user_and_email_scheme(self):
        # Setup new scheme with all question types as auth fields and create existing scheme account
        new_external_id = "Test User store email lowercase"
        new_user = UserFactory(external_id=new_external_id, client=self.client_app, email=new_external_id)
        auth_header = self._get_auth_header(new_user)
        scheme = SchemeFactory()
        SchemeBundleAssociationFactory(scheme=scheme, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE)
        card_num_question = SchemeCredentialQuestionFactory(
            scheme=scheme,
            type=CARD_NUMBER,
            label=CARD_NUMBER,
            manual_question=True,
            add_field=True,
        )
        email_question = SchemeCredentialQuestionFactory(
            scheme=scheme,
            type=EMAIL,
            label=EMAIL,
            auth_field=True,
            enrol_field=True,
            register_field=True,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
        )

        return new_user, scheme, card_num_question, email_question, auth_header

    def test_get_single_payment_card(self, *_):
        payment_card_account = self.payment_card_account_entry.payment_card_account
        expected_result = remove_empty(PaymentCardSerializer(payment_card_account).data)
        resp = self.client.get(reverse("payment-card", args=[payment_card_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    def test_update_payment_card(self):
        payment_card_account = self.payment_card_account_entry.payment_card_account
        new_data = {"card": {"name_on_card": "new name on card"}}
        resp = self.client.patch(
            reverse("payment-card", args=[payment_card_account.id]),
            data=json.dumps(new_data),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["card"]["name_on_card"], new_data["card"]["name_on_card"])

        new_consent = {"account": {"consents": [{"timestamp": 23947329497, "type": 0}]}}
        resp = self.client.patch(
            reverse("payment-card", args=[payment_card_account.id]),
            data=json.dumps(new_consent),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["account"]["consents"], new_consent["account"]["consents"])

    def test_get_all_payment_cards(self):
        PaymentCardAccountEntryFactory(user=self.user)
        payment_card_accounts = PaymentCardAccount.objects.filter(user_set__id=self.user.id).all()
        expected_result = remove_empty(PaymentCardSerializer(payment_card_accounts, many=True).data)
        resp = self.client.get(reverse("payment-cards"), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_get_single_membership_card(self, mock_get_midas_balance, *_):
        mock_get_midas_balance.return_value = self.scheme_account.balances
        resp = self.client.get(reverse("membership-card", args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

        self.scheme_bundle_association.test_scheme = True
        self.scheme_bundle_association.status = SchemeBundleAssociation.ACTIVE
        self.scheme_bundle_association.save()
        resp = self.client.get(reverse("membership-card", args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 404)

        self.user.is_tester = True
        self.user.save()
        resp = self.client.get(reverse("membership-card", args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

        self.user.is_tester = False
        self.user.save()
        self.scheme_bundle_association.test_scheme = False
        self.scheme_bundle_association.save()

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_get_all_membership_cards(self, *_):
        scheme_account_2 = SchemeAccountFactory(balances=self.scheme_account.balances)
        bundle_assoc = SchemeBundleAssociationFactory(
            scheme=scheme_account_2.scheme, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE
        )
        SchemeAccountEntryFactory(scheme_account=scheme_account_2, user=self.user)
        scheme_accounts = SchemeAccount.objects.filter(user_set__id=self.user.id).all()
        expected_result = remove_empty(
            MembershipCardSerializer(scheme_accounts, many=True, context={"user_id": self.user.id}).data
        )
        resp = self.client.get(reverse("membership-cards"), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result[0]["account"], resp.json()[0]["account"])
        self.assertEqual(len(resp.json()), 2)

        bundle_assoc.test_scheme = True
        bundle_assoc.save()
        resp = self.client.get(reverse("membership-cards"), **self.auth_headers)
        self.assertEqual(len(resp.json()), 1)

        self.user.is_tester = True
        self.user.save()
        resp = self.client.get(reverse("membership-cards"), **self.auth_headers)
        self.assertEqual(len(resp.json()), 2)

        self.user.is_tester = False
        self.user.save()
        bundle_assoc.test_scheme = False
        bundle_assoc.save()

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_get_single_membership_vouchers(self, mock_get_midas_balance, *_):
        mock_get_midas_balance.return_value = self.scheme_account.balances
        resp = self.client.get(reverse("membership-card", args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

        vouchers = resp.data["vouchers"]

        self.assertEqual(len(vouchers), 4)
        self.assertEqual(vouchers[0]["state"], "issued")
        self.assertEqual(vouchers[0]["code"], self.scheme_account.vouchers[0]["code"])

        self.assertEqual(vouchers[1]["state"], "expired")
        self.assertEqual(vouchers[1]["code"], "")

        self.assertEqual(vouchers[2]["state"], "redeemed")
        self.assertEqual(vouchers[2]["code"], "")

        self.assertEqual(vouchers[3]["state"], "cancelled")
        self.assertEqual(vouchers[3]["code"], "")

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_list_membership_cards_hides_join_cards(self, *_):
        join_scheme_account = SchemeAccountFactory()
        SchemeBundleAssociationFactory(
            scheme=join_scheme_account.scheme, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE
        )
        SchemeAccountEntryFactory(
            scheme_account=join_scheme_account, user=self.user, link_status=AccountLinkStatus.JOIN
        )
        scheme_account_entries = SchemeAccountEntry.objects.filter(
            user_id=self.user.id, link_status=AccountLinkStatus.JOIN
        ).all()
        join_ids = [sae.scheme_account.id for sae in scheme_account_entries]

        resp = self.client.get(reverse("membership-cards"), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        resp_join_ids = [card["id"] for card in resp.json()]
        for join_id in join_ids:
            self.assertFalse(join_id in resp_join_ids)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_creation(self, *_):
        payload = {
            "card": {
                "last_four_digits": 5234,
                "currency_code": "GBP",
                "first_six_digits": 423456,
                "name_on_card": "test user 2",
                "token": "H7FdKWKPOPhepzxS4MfUuvTDHxr",
                "fingerprint": "b5fe350d5135ab64a8f3c1097fadefd9effb",
                "year": 22,
                "month": 3,
                "order": 1,
            },
            "account": {"consents": [{"timestamp": 1517549941, "type": 0}]},
        }

        resp = self.client.post(
            reverse("payment-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
            **self.version_header,
        )
        self.assertEqual(resp.status_code, 201)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_creation_other_wallet_same_fingerprint(self, *_):
        payload = {
            "card": {
                "last_four_digits": 5234,
                "currency_code": "GBP",
                "first_six_digits": 423456,
                "name_on_card": "test user 2",
                "token": "H7FdKWKPOPhepzxS4MfUuvTDHxr",
                "fingerprint": "b5fe350d5135ab64a8f3c1097fadefd9effb",
                "year": 22,
                "month": 3,
                "order": 1,
            },
            "account": {"consents": [{"timestamp": 1517549941, "type": 0}]},
        }

        resp = self.client.post(
            reverse("payment-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
            **self.version_header,
        )
        self.assertEqual(resp.status_code, 201)

        resp2 = self.client.post(
            reverse("payment-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers_user2,
            **self.version_header,
        )
        self.assertEqual(resp2.status_code, 201)
        card = PaymentCardAccount.all_objects.get(fingerprint=payload["card"]["fingerprint"])
        self.assertEqual(card.expiry_year, payload["card"]["year"])
        self.assertEqual(card.expiry_month, payload["card"]["month"])
        self.assertEqual(card.is_deleted, False)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_creation_other_wallet_date_changed(self, *_):
        payload = {
            "card": {
                "last_four_digits": 5234,
                "currency_code": "GBP",
                "first_six_digits": 423456,
                "name_on_card": "test user 2",
                "token": "H7FdKWKPOPhepzxS4MfUuvTDHxr",
                "fingerprint": "b5fe350d5135ab64a8f3c1097fadefd9effb",
                "year": 22,
                "month": 3,
                "order": 1,
            },
            "account": {"consents": [{"timestamp": 1517549941, "type": 0}]},
        }

        resp = self.client.post(
            reverse("payment-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
            **self.version_header,
        )
        self.assertEqual(resp.status_code, 201)
        card = PaymentCardAccount.all_objects.get(fingerprint=payload["card"]["fingerprint"])
        self.assertEqual(card.expiry_year, payload["card"]["year"])
        self.assertEqual(card.expiry_month, payload["card"]["month"])
        self.assertEqual(card.is_deleted, False)

        payload["card"]["year"] = 24
        payload["card"]["month"] = 6

        resp2 = self.client.post(
            reverse("payment-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers_user2,
            **self.version_header,
        )
        self.assertEqual(resp2.status_code, 201)
        card = PaymentCardAccount.all_objects.get(fingerprint=payload["card"]["fingerprint"])
        self.assertEqual(card.expiry_year, payload["card"]["year"])
        self.assertEqual(card.expiry_month, payload["card"]["month"])
        self.assertEqual(card.is_deleted, False)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_creation_with_id_fails_when_not_internal_user(self, *_):
        payload = {
            "card": {
                "last_four_digits": 5234,
                "currency_code": "GBP",
                "first_six_digits": 423456,
                "name_on_card": "test user 2",
                "token": "H7FdKWKPOPhepzxS4MfUuvTDHxz",
                "fingerprint": "b5fe350d5135ab64a8f3c1097fadefd9effz",
                "year": 22,
                "month": 3,
                "order": 1,
            },
            "account": {"consents": [{"timestamp": 1517549941, "type": 0}]},
        }
        provided_id = 150000000

        resp = self.client.post(
            reverse("payment-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_OBJECT_ID=provided_id,
            **self.auth_headers,
            **self.version_header,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertNotEqual(resp.json()["id"], provided_id)

    @patch("payment_card.metis.enrol_new_payment_card")
    def test_payment_card_replace(self, *_):
        pca = PaymentCardAccountFactory(token="original-token")
        PaymentCardAccountEntryFactory(user=self.user, payment_card_account=pca)
        correct_payload = {
            "card": {
                "last_four_digits": "5234",
                "currency_code": "GBP",
                "first_six_digits": "423456",
                "name_on_card": "test user 2",
                "token": "token-to-ignore",
                "fingerprint": str(pca.fingerprint),
                "year": 22,
                "month": 3,
                "order": 1,
            },
            "account": {"consents": [{"timestamp": 1517549941, "type": 0}]},
        }
        resp = self.client.put(
            reverse("payment-card", args=[pca.id]),
            data=json.dumps(correct_payload),
            content_type="application/json",
            **self.auth_headers,
            **self.version_header,
        )
        pca.refresh_from_db()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(pca.token, "original-token")
        self.assertEqual(pca.pan_end, correct_payload["card"]["last_four_digits"])

        wrong_payload = {
            "card": {
                "last_four_digits": "5234",
                "currency_code": "GBP",
                "first_six_digits": "423456",
                "name_on_card": "test user 2",
                "token": "token-to-ignore",
                "fingerprint": "this-is-not-{}".format(pca.fingerprint),
                "year": 22,
                "month": 3,
                "order": 1,
            },
            "account": {"consents": [{"timestamp": 1517549941, "type": 0}]},
        }
        resp = self.client.put(
            reverse("payment-card", args=[pca.id]),
            data=json.dumps(wrong_payload),
            content_type="application/json",
            **self.auth_headers,
            **self.version_header,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "cannot override fingerprint.")

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.views.async_balance_with_updated_credentials", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_membership_card_status_mapping_active(self, *_):
        self.scheme_account_entry.link_status = AccountLinkStatus.ACTIVE
        self.scheme_account_entry.save()
        data = MembershipCardSerializer(
            self.scheme_account,
            context={"user_id": self.user.id},
        ).data
        self.assertEqual(data["status"]["state"], "authorised")
        self.assertEqual(data["status"]["reason_codes"], ["X300"])

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.views.async_balance_with_updated_credentials", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_membership_card_status_mapping_user_error(self, *_):
        user_error = AccountLinkStatus.INVALID_CREDENTIALS
        self.scheme_account_entry.link_status = user_error
        self.scheme_account.balances = {}
        self.scheme_account.save()
        self.scheme_account_entry.save()

        data = MembershipCardSerializer(
            self.scheme_account,
            context={"user_id": self.user.id},
        ).data
        self.assertEqual(data["status"]["state"], "failed")
        self.assertEqual(data["status"]["reason_codes"], ["X303"])

        self.scheme_account.balances = [{"points": 1.1}]
        self.scheme_account.save()

        data = MembershipCardSerializer(
            self.scheme_account,
            context={"user_id": self.user.id},
        ).data
        self.assertEqual(data["status"]["state"], "failed")
        self.assertEqual(data["status"]["reason_codes"], ["X303"])

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.views.async_balance_with_updated_credentials", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_membership_card_status_mapping_system_error(self, *_):
        user_error = AccountLinkStatus.END_SITE_DOWN
        self.scheme_account_entry.link_status = user_error
        self.scheme_account_entry.save()

        self.scheme_account.balances = {}
        self.scheme_account.save()

        data = MembershipCardSerializer(
            self.scheme_account,
            context={"user_id": self.user.id},
        ).data
        self.assertEqual("pending", data["status"]["state"])
        self.assertEqual(["X100"], data["status"]["reason_codes"])

        self.scheme_account.balances = [{"points": 1.1}]
        self.scheme_account.save()

        data = MembershipCardSerializer(
            self.scheme_account,
            context={"user_id": self.user.id},
        ).data
        self.assertEqual("authorised", data["status"]["state"])
        self.assertEqual(["X300"], data["status"]["reason_codes"])

    def test_membership_card_V1_3_returns_default_error_message_if_no_override_exists(self, *_):
        self.scheme_account_entry.link_status = AccountLinkStatus.ACCOUNT_ALREADY_EXISTS
        self.scheme_account_entry.save()
        error_messages = dict((code, message) for code, message in CURRENT_STATUS_CODES)
        data = MembershipCardSerializer_V1_3(
            self.scheme_account,
            context={"user_id": self.user.id},
        ).data
        self.assertEqual(error_messages[445], data["status"]["error_text"])

    def test_membership_card_V1_3_contains_custom_error_message(self, *_):
        self.scheme_account_entry.link_status = AccountLinkStatus.ACCOUNT_ALREADY_EXISTS
        self.scheme_account_entry.save()
        error = SchemeOverrideError(
            scheme_id=self.scheme_account.scheme_id,
            error_slug="ACCOUNT_ALREADY_EXISTS",
            error_code=445,
            reason_code="X202",
            message="Custom error message",
        )
        error.save()

        data = MembershipCardSerializer_V1_3(
            self.scheme_account,
            context={"user_id": self.user.id},
        ).data
        self.assertEqual("Custom error message", data["status"]["error_text"])

    # Test falls in the pipeline - to be investigated.
    # def test_membership_card_V1_3_override_system_error(self, *_):
    #     self.scheme_account.status = SchemeAccount.UNKNOWN_ERROR
    #     self.scheme_account.save()
    #     error = SchemeOverrideError(scheme_id=self.scheme_account.scheme_id,
    #                                 error_slug='UNKNOWN_ERROR',
    #                                 error_code=520,
    #                                 reason_code='X202',
    #                                 message='Custom system error message')
    #     error.save()
    #     data = MembershipCardSerializer_V1_3(self.scheme_account).data
    #     self.assertEqual('Custom system error message', data['status']['error_text'])

    def test_membership_card_serializer_base_V1_2_contains_no_error_message(self):
        self.scheme_account_entry.link_status = AccountLinkStatus.ACCOUNT_ALREADY_EXISTS
        self.scheme_account_entry.save()

        data = MembershipCardSerializer_base(
            self.scheme_account,
            context={"user_id": self.user.id},
        ).data
        status = {"state": "failed", "reason_codes": ["X202"]}
        self.assertEqual(status, data["status"])

        data = MembershipCardSerializer(
            self.scheme_account,
            context={"user_id": self.user.id},
        ).data
        self.assertEqual(status, data["status"])

    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    def test_membership_card_creation(self, mock_async_balance, mock_async_link, *_):
        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [{"column": self.scheme.manual_question.label, "value": "3038401022657083"}],
                "authorise_fields": [{"column": self.secondary_question.label, "value": "Test"}],
            },
        }
        resp = self.client.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **self.auth_headers
        )
        self.assertEqual(resp.status_code, 201)
        create_data = resp.data

        sa = SchemeAccount.objects.get(pk=create_data["id"])
        self.assertEqual(sa.barcode, payload["account"]["add_fields"][0]["value"])
        self.assertEqual(sa.originating_journey, JourneyTypes.ADD)

        # replay and check data with 200 response
        resp = self.client.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **self.auth_headers
        )
        self.assertEqual(resp.status_code, 200)
        # data not the same since we added auth_pending / add_auth_pending status
        status = {"state": "pending", "reason_codes": ["X100"], "error_text": "Add Auth Pending"}

        self.assertEqual(status, resp.data["status"])
        # remove the status field then check the dict's are equal
        del resp.data["status"]
        del create_data["status"]
        self.assertDictEqual(resp.data, create_data)
        self.assertTrue(mock_async_link.delay.called)
        self.assertFalse(mock_async_balance.delay.called)

    # todo: fix as part of TC phase 3+
    # @patch("ubiquity.influx_audit.InfluxDBClient")
    # @patch("ubiquity.views.async_link", autospec=True)
    # @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    # def test_wallet_only_mcard_creation(self, mock_async_balance, mock_async_link, *_):
    #     payload = {
    #         "membership_plan": self.scheme.id,
    #         "account": {"add_fields": [{"column": self.scheme.manual_question.label, "value": "3038401022657083"}]},
    #     }
    #     resp = self.client.post(
    #         reverse("membership-cards"), data=json.dumps(payload), content_type="application/json",
    #         **self.auth_headers
    #     )
    #     self.assertEqual(resp.status_code, 201)
    #     self.assertEqual(
    #         {"state": "unauthorised", "reason_codes": ["X103"], "error_text": "Wallet only card"}, resp.data["status"]
    #     )
    #     create_data = resp.data
    #
    #     sa = SchemeAccount.objects.get(pk=create_data["id"])
    #     self.assertEqual(sa.barcode, payload["account"]["add_fields"][0]["value"])
    #     self.assertEqual(sa.originating_journey, JourneyTypes.ADD)
    #
    #     # replay and check same data with 200 response
    #     resp = self.client.post(
    #         reverse("membership-cards"), data=json.dumps(payload), content_type="application/json",
    #         **self.auth_headers
    #     )
    #     self.assertEqual(resp.status_code, 200)
    #     self.assertDictEqual(resp.data, create_data)
    #     self.assertEqual(
    #         {"state": "unauthorised", "reason_codes": ["X103"], "error_text": "Wallet only card"}, resp.data["status"]
    #     )
    #     self.assertFalse(mock_async_link.delay.called)
    #     self.assertFalse(mock_async_balance.delay.called)

    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    def test_link_user_to_existing_wallet_only_card(self, mock_analytics, *_):
        test_schemes = (
            (self.wallet_only_scheme, self.wallet_only_question),
            (self.scheme, self.scheme.manual_question),
        )

        new_user = UserFactory(client=self.client_app, external_id="testexternalid")
        headers = {"HTTP_AUTHORIZATION": "{}".format(self._get_auth_header(new_user))}
        for scheme, question in test_schemes:
            existing_answer_value = "1234554321"
            existing_scheme_account = SchemeAccountFactory(scheme=scheme, **{question.type: existing_answer_value})
            scheme_account_entry = SchemeAccountEntryFactory(scheme_account=existing_scheme_account, user=self.user)
            SchemeCredentialAnswerFactory(
                question=question,
                answer=existing_answer_value,
                scheme_account_entry=scheme_account_entry,
            )

            payload = {
                "membership_plan": scheme.id,
                "account": {"add_fields": [{"column": question.label, "value": existing_answer_value}]},
            }
            resp = self.client.post(
                reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **headers
            )
            self.assertEqual(resp.status_code, 200)
            card_id = resp.json()["id"]

            user_links = SchemeAccountEntry.objects.filter(scheme_account=existing_scheme_account).values_list(
                "user_id", flat=True
            )

            self.assertIn(self.user.id, user_links)
            self.assertIn(new_user.id, user_links)

            # check card is in get membership_cards response
            resp = self.client.get(reverse("membership-cards"), content_type="application/json", **headers)
            self.assertEqual(resp.status_code, 200)
            card_ids = [card["id"] for card in resp.json()]
            self.assertIn(card_id, card_ids)

    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    def test_wallet_only_mcard_authorisation(self, *_):
        existing_answer_value = "34567876345678765"
        existing_scheme_account = SchemeAccountFactory(scheme=self.scheme, barcode=existing_answer_value)
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=existing_scheme_account, user=self.user, link_status=AccountLinkStatus.WALLET_ONLY
        )
        SchemeCredentialAnswerFactory(
            question=self.scheme.manual_question,
            answer=existing_answer_value,
            scheme_account_entry=scheme_account_entry,
        )

        new_user = UserFactory(client=self.client_app, external_id="testexternalid")
        headers = {"HTTP_AUTHORIZATION": "{}".format(self._get_auth_header(new_user))}
        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [{"column": self.scheme.manual_question.label, "value": existing_answer_value}],
                "authorise_fields": [{"column": self.secondary_question.label, "value": "Test"}],
            },
        }
        resp = self.client.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **headers
        )
        resp_json = resp.json()
        card_id = resp_json["id"]

        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            # was
            # resp_json["status"], {"state": "unauthorised", "reason_codes": ["X103"], "error_text": "Wallet only card"}
            # now 2nd user is pending until response from Midas responds (ie background tasks mocked out run)
            resp_json["status"],
            {"state": "pending", "reason_codes": ["X100"], "error_text": "Pending"},
        )

        user_links = SchemeAccountEntry.objects.filter(scheme_account=existing_scheme_account)

        linked_users = [link.user_id for link in user_links]
        self.assertIn(self.user.id, linked_users)
        self.assertIn(new_user.id, linked_users)

        # check card is in get membership_cards response
        resp = self.client.get(reverse("membership-cards"), content_type="application/json", **headers)
        self.assertEqual(resp.status_code, 200)
        card_ids = [card["id"] for card in resp.json()]
        self.assertIn(card_id, card_ids)

    def test_wallet_only_authorised_card_already_exists(self, *_):
        existing_answer_value = "34567876345678765"
        existing_scheme_account = SchemeAccountFactory(scheme=self.scheme, barcode=existing_answer_value)
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=existing_scheme_account,
            user=self.user,
            link_status=AccountLinkStatus.WALLET_ONLY,
        )
        SchemeCredentialAnswerFactory(
            question=self.scheme.manual_question,
            answer=existing_answer_value,
            scheme_account_entry=scheme_account_entry,
        )

        payload = {
            "membership_plan": self.scheme.id,
            "account": {"add_fields": [{"column": self.scheme.manual_question.label, "value": existing_answer_value}]},
        }
        resp = self.client.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **self.auth_headers
        )
        resp_json = resp.json()

        self.assertEqual(400, resp.status_code)
        self.assertEqual("Card already exists in your wallet", resp_json["detail"])

        user_links = SchemeAccountEntry.objects.filter(scheme_account=existing_scheme_account)

        linked_users = [link.user_id for link in user_links]
        self.assertIn(self.user.id, linked_users)
        # self.assertTrue(all([link.auth_provided for link in user_links]))

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("ubiquity.influx_audit.InfluxDBClient")
    def test_autolink_for_wallet_only_mcard_does_not_soft_link(self, *_):
        self.payment_card_account.status = PaymentCardAccount.ACTIVE
        self.payment_card_account.save()

        payload = {
            "membership_plan": self.scheme.id,
            "account": {"add_fields": [{"column": self.scheme.manual_question.label, "value": "3038401022657083"}]},
        }

        resp = self.client.post(
            f"{reverse('membership-cards')}/?autoLink=True",
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(resp.status_code, 201)

        mcard_id = resp.data["id"]
        with self.assertRaises(PaymentCardSchemeEntry.DoesNotExist):
            PaymentCardSchemeEntry.objects.get(scheme_account=mcard_id, payment_card_account=self.payment_card_account)

    def test_manual_linking_for_wallet_only_mcard_does_not_create_soft_link(self):
        existing_answer_value = "36543456787656"
        existing_scheme_account = SchemeAccountFactory(scheme=self.scheme, barcode=existing_answer_value)
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=existing_scheme_account,
            user=self.user,
            link_status=AccountLinkStatus.WALLET_ONLY,
        )
        SchemeCredentialAnswerFactory(
            question=self.scheme.manual_question,
            answer=existing_answer_value,
            scheme_account_entry=scheme_account_entry,
        )

        resp = self.client.patch(
            reverse(
                "membership-link",
                kwargs={"pcard_id": self.payment_card_account.id, "mcard_id": existing_scheme_account.id},
            ),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(resp.status_code, 404)

        with self.assertRaises(PaymentCardSchemeEntry.DoesNotExist):
            PaymentCardSchemeEntry.objects.get(
                scheme_account=existing_scheme_account.id, payment_card_account=self.payment_card_account.id
            ).get_instance_with_active_status()

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    def test_wallet_only_card_patch_fails(self):
        existing_answer_value = "36543456787656"
        existing_scheme_account = SchemeAccountFactory(scheme=self.scheme, barcode=existing_answer_value)
        entry = SchemeAccountEntryFactory(
            scheme_account=existing_scheme_account,
            user=self.user,
            link_status=AccountLinkStatus.WALLET_ONLY,
        )
        SchemeAccountEntryFactory(
            scheme_account=existing_scheme_account,
            user=self.user2,
            link_status=AccountLinkStatus.WALLET_ONLY,
        )

        SchemeCredentialAnswerFactory(
            question=self.scheme.manual_question,
            answer=existing_answer_value,
            scheme_account_entry=entry,
        )

        payload = {
            "membership_plan": self.scheme.id,
            "account": {"authorise_fields": [{"column": self.secondary_question.label, "value": "Test"}]},
        }

        resp = self.client.patch(
            reverse("membership-card", kwargs={"pk": existing_scheme_account.id}),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(400, resp.status_code)
        self.assertEqual(
            "Cannot update authorise fields for Store type card. Card must be authorised "
            "via POST /membership_cards endpoint first.",
            resp.data["detail"],
        )

    @patch("ubiquity.views.async_link", autospec=True)
    def test_membership_card_link_with_consents(self, *_):
        consent_label = "Test Consent"
        consent = ConsentFactory.create(scheme=self.scheme)

        ThirdPartyConsentLink.objects.create(
            consent_label=consent_label,
            client_app=self.client_app,
            scheme=self.scheme,
            consent=consent,
            add_field=False,
            auth_field=True,
            register_field=False,
            enrol_field=False,
        )

        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [{"column": "barcode", "value": "3038401022657083"}],
                "authorise_fields": [{"column": "last_name", "value": "Test"}],
            },
        }
        resp = self.client.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **self.auth_headers
        )
        self.assertEqual(resp.status_code, 400)

        payload["account"]["authorise_fields"].append({"column": consent_label, "value": "true"})

        resp = self.client.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **self.auth_headers
        )
        self.assertEqual(resp.status_code, 201)

    def test_membership_card_creation_consents(self):
        factory = RequestFactory()
        consent_label = "Test Consent"
        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "enrol_fields": [{"column": "last_name", "value": "Test"}, {"column": consent_label, "value": "true"}]
            },
        }
        request = factory.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **self.auth_headers
        )

        user = MagicMock()
        user.client = self.client_app
        request.user = user
        request.channels_permit = ChannelPermitMock(self.client_app)
        view = MembershipCardView()
        view.request = request

        consent = ConsentFactory.create(scheme=self.scheme)

        ThirdPartyConsentLink.objects.create(
            consent_label=consent_label,
            client_app=self.client_app,
            scheme=self.scheme,
            consent=consent,
            add_field=False,
            auth_field=False,
            register_field=True,
            enrol_field=True,
        )

        consents = view._extract_consent_data(scheme=self.scheme, field="enrol_fields", data=payload)

        self.assertEqual(consents, {"consents": [{"id": consent.id, "value": "true"}]})

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.views.async_join", autospec=True)
    @patch("payment_card.payment.get_secret_key", autospec=True)
    def test_membership_card_enrol_with_main_answer(self, mock_secret, mock_async_join, mock_async_balance):
        mock_secret.return_value = "test_secret"
        external_id = "anothertest@user.com"
        user = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        auth_headers = {"HTTP_AUTHORIZATION": "{}".format(self._get_auth_header(user))}

        consent_label = "Consent 1"
        consent = ConsentFactory.create(scheme=self.scheme, journey=JourneyTypes.JOIN.value)

        ThirdPartyConsentLink.objects.create(
            consent_label=consent_label,
            client_app=self.client_app,
            scheme=self.scheme,
            consent=consent,
            add_field=False,
            auth_field=False,
            register_field=True,
            enrol_field=True,
        )

        main_answer = "1111111111111111111"

        payload = {
            "account": {
                "enrol_fields": [
                    {"column": BARCODE, "value": main_answer},
                    {"column": LAST_NAME, "value": "New last name"},
                    {"column": consent_label, "value": "True"},
                ]
            },
            "membership_plan": self.scheme.id,
        }
        response = self.client.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **auth_headers
        )

        self.assertEqual(response.status_code, 201)
        scheme_account = SchemeAccount.objects.get(pk=response.json()["id"])
        scheme_account_entry = SchemeAccountEntry.objects.get(scheme_account=scheme_account, user=user)
        self.assertEqual(scheme_account.barcode, main_answer)
        self.assertIn(scheme_account_entry.link_status, AccountLinkStatus.join_pending())
        self.assertEqual(scheme_account.originating_journey, JourneyTypes.JOIN)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("api_messaging.midas_messaging.to_midas", autospec=True, return_value=MagicMock())
    @patch("payment_card.payment.get_secret_key", autospec=True)
    def test_membership_card_enrol_midas_message(self, mock_secret, mock_message, mock_async_balance):
        mock_secret.return_value = "test_secret"
        external_id = "anothertest@user.com"
        user = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        auth_headers = {"HTTP_AUTHORIZATION": "{}".format(self._get_auth_header(user))}

        consent_label = "Consent 1"
        consent = ConsentFactory.create(scheme=self.scheme, journey=JourneyTypes.JOIN.value)

        ThirdPartyConsentLink.objects.create(
            consent_label=consent_label,
            client_app=self.client_app,
            scheme=self.scheme,
            consent=consent,
            add_field=False,
            auth_field=False,
            register_field=True,
            enrol_field=True,
        )

        main_answer = "1111111111111111111"

        payload = {
            "account": {
                "enrol_fields": [
                    {"column": BARCODE, "value": main_answer},
                    {"column": LAST_NAME, "value": "New last name"},
                    {"column": consent_label, "value": "True"},
                ]
            },
            "membership_plan": self.scheme.id,
        }
        response = self.client.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **auth_headers
        )

        scheme_account = SchemeAccount.objects.get(pk=response.json()["id"])

        self.assertTrue(mock_message.called)
        message = mock_message.call_args.args[0]
        headers = message.metadata
        body = message.body
        self.assertIsInstance(message, JoinApplication)
        self.assertEqual(len(body), 1)
        self.assertIsInstance(body["join_data"]["encrypted_credentials"], str)
        self.assertEqual(headers["type"], "loyalty_account.join.application")
        self.assertEqual(headers["channel"], "test.auth.fake")
        self.assertEqual(headers["loyalty-plan"], scheme_account.scheme.slug)
        self.assertEqual(headers["request-id"], str(scheme_account.id))
        self.assertEqual(headers["account-id"], scheme_account.barcode)
        self.assertEqual(headers["bink-user-id"], str(user.id))
        self.assertIsInstance(headers["transaction-id"], str)

    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch("ubiquity.views.async_join", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    @patch("payment_card.payment.get_secret_key", autospec=True)
    def test_membership_card_jwp_fails_with_bad_payment_card(self, mock_get_hash_secret, *_):
        mock_get_hash_secret.return_value = "testsecret"
        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "enrol_fields": [
                    {"column": LAST_NAME, "value": "last name"},
                    {"column": PAYMENT_CARD_HASH, "value": "nonexistenthash"},
                ]
            },
        }
        resp = self.client.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **self.auth_headers
        )

        self.assertTrue(mock_get_hash_secret.called)
        self.assertEqual(resp.status_code, 400)
        error_message = resp.json()["detail"]
        self.assertEqual(error_message, "Provided payment card could not be found or is not related to this user")

    @patch("ubiquity.views.async_balance_with_updated_credentials.delay", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_membership_card_update(self, *_):
        payload = json.dumps(
            {
                "account": {
                    "add_fields": [{"column": "barcode", "value": self.scheme_account_answer.answer}],
                    "authorise_fields": [{"column": "last_name", "value": "Test"}],
                }
            }
        )
        response = self.client.patch(
            reverse("membership-card", args=[self.scheme_account.id]),
            content_type="application/json",
            data=payload,
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)

        self.scheme_bundle_association.test_scheme = True
        self.scheme_bundle_association.status = SchemeBundleAssociation.ACTIVE
        self.scheme_bundle_association.save()
        response = self.client.patch(
            reverse("membership-card", args=[self.scheme_account.id]),
            content_type="application/json",
            data=payload,
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 404)

        self.user.is_tester = True
        self.user.save()

        # Must set active in order for re-patch to work and show result of test user
        self.scheme_account_entry.link_status = AccountLinkStatus.ACTIVE
        self.scheme_account_entry.save()

        response = self.client.patch(
            reverse("membership-card", args=[self.scheme_account.id]),
            content_type="application/json",
            data=payload,
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)

        self.scheme_bundle_association.test_scheme = False
        self.scheme_bundle_association.save()
        self.user.is_tester = False
        self.user.save()

    @patch("ubiquity.views.async_balance_with_updated_credentials.delay", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_membership_card_update_key_cred_to_existing(self, *_):
        scheme_account2 = SchemeAccountFactory(scheme=self.scheme)
        scheme_account_entry2 = SchemeAccountEntryFactory.create(scheme_account=scheme_account2, user=self.user2)

        existing_answer = "some existing answer"
        SchemeCredentialAnswerFactory(
            question=self.scheme.manual_question,
            answer=existing_answer,
            scheme_account_entry=scheme_account_entry2,
        )
        SchemeCredentialAnswerFactory(
            question=self.secondary_question,
            scheme_account_entry=scheme_account_entry2,
        )
        scheme_account_entry2.update_scheme_account_key_credential_fields()

        payload = json.dumps(
            {
                "account": {
                    "add_fields": [{"column": "barcode", "value": existing_answer}],
                    "authorise_fields": [{"column": "last_name", "value": "Test"}],
                }
            }
        )
        response = self.client.patch(
            reverse("membership-card", args=[self.scheme_account.id]),
            content_type="application/json",
            data=payload,
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(AccountLinkStatus.FAILED_UPDATE, self.scheme_account_entry.link_status)

        answer_before = self.scheme_account_answer.answer
        self.scheme_account_answer.refresh_from_db()
        self.assertEqual(answer_before, self.scheme_account_answer.answer)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.tasks.remove_loyalty_card_event")
    def test_membership_card_delete(self, mock_to_warehouse, *_):
        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [{"column": "barcode", "value": "3038401022657082131"}],
                "authorise_fields": [{"column": "last_name", "value": "Testy"}],
            },
        }
        resp = self.client.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **self.auth_headers
        )
        self.assertEqual(resp.status_code, 201)
        create_data = resp.data
        # replay and check same data with 200 response
        resp = self.client.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **self.auth_headers
        )
        self.assertEqual(resp.status_code, 200)
        # data not the same since we added auth_pending / add_auth_pending status
        status = {"state": "pending", "reason_codes": ["X100"], "error_text": "Add Auth Pending"}

        self.assertEqual(status, resp.data["status"])
        # remove the status field then check the dict's are equal
        del resp.data["status"]
        del create_data["status"]
        self.assertDictEqual(resp.data, create_data)
        account_id = resp.data["id"]

        resp_del = self.client.delete(
            reverse("membership-card", args=[account_id]),
            data="{}",
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(resp_del.status_code, 200)
        resp2 = self.client.post(
            reverse("membership-cards"), data=json.dumps(payload), content_type="application/json", **self.auth_headers
        )
        self.assertEqual(resp2.status_code, 201)
        self.assertEqual(mock_to_warehouse.call_count, 1)

    def test_membership_card_delete_error_on_pending_join_mcard(self):
        scheme_account = SchemeAccountFactory(scheme=self.scheme)
        SchemeAccountEntryFactory(
            scheme_account=scheme_account,
            user=self.user,
            link_status=AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS,
        )

        resp = self.client.delete(
            reverse("membership-card", args=[scheme_account.id]), content_type="application/json", **self.auth_headers
        )

        self.assertEqual(resp.status_code, 405)
        self.assertEqual(
            resp.json(), {"join_pending": "Membership card cannot be deleted until the " "Join process has completed."}
        )

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_cards_linking(self, *_):
        payment_card_account = self.payment_card_account_entry.payment_card_account
        scheme_account_2 = SchemeAccountFactory(scheme=self.scheme)
        SchemeAccountEntryFactory(user=self.user, scheme_account=scheme_account_2)

        params = [payment_card_account.id, self.scheme_account.id]
        resp = self.client.patch(reverse("membership-link", args=params), **self.auth_headers)
        self.assertEqual(resp.status_code, 201)

        params = [payment_card_account.id, scheme_account_2.id]
        resp = self.client.patch(reverse("membership-link", args=params), **self.auth_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("PLAN_ALREADY_LINKED", resp.json())

    """
     This test hangs up on web2 when tested on server but passes locally
    def test_membership_card_delete_does_not_delete_link_for_cards_shared_between_users(self):
        external_id = 'test2@user.com'
        user_2 = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        SchemeAccountEntryFactory(user=user_2, scheme_account=self.scheme_account)
        PaymentCardAccountEntryFactory(user=user_2,
                                       payment_card_account=self.payment_card_account)

        entry = PaymentCardSchemeEntry.objects.create(payment_card_account=self.payment_card_account,
                                                      scheme_account=self.scheme_account)

        resp = self.client.delete(reverse('membership-card', args=[self.scheme_account.id]),
                                  data="{}",
                                  content_type='application/json', **self.auth_headers)

        self.assertEqual(resp.status_code, 200)

        link = PaymentCardSchemeEntry.objects.filter(pk=entry.pk)
        self.assertEqual(len(link), 1)
    """

    @patch("ubiquity.tasks.remove_loyalty_card_event")
    @patch("ubiquity.views.deleted_membership_card_cleanup.delay", autospec=True)
    def test_membership_card_delete_removes_link_for_cards_not_shared_between_users(
        self, mock_delete, mock_to_warehouse
    ):
        entry = PaymentCardSchemeEntry.objects.create(
            payment_card_account=self.payment_card_account, scheme_account=self.scheme_account
        )
        resp = self.client.delete(
            reverse("membership-card", args=[self.scheme_account.id]),
            data="{}",
            content_type="application/json",
            **self.auth_headers,
        )
        clean_up_args = mock_delete.call_args
        self.assertTrue(mock_delete.called)
        deleted_membership_card_cleanup(*clean_up_args[0], **clean_up_args[1])
        self.assertEqual(resp.status_code, 200)
        link = PaymentCardSchemeEntry.objects.filter(pk=entry.pk)
        self.assertEqual(len(link), 0)
        self.assertEqual(mock_to_warehouse.call_count, 1)

    """
    This test hangs up on web2 when tested on server but passes locally
    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                       CELERY_TASK_ALWAYS_EAGER=True,
                       BROKER_BACKEND='memory')
    def test_payment_card_delete_does_not_delete_link_for_cards_shared_between_users(self):
        external_id = 'test2@user.com'
        user_2 = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        SchemeAccountEntryFactory(user=user_2, scheme_account=self.scheme_account)
        PaymentCardAccountEntryFactory(user=user_2,
                                       payment_card_account=self.payment_card_account)

        entry = PaymentCardSchemeEntry.objects.create(payment_card_account=self.payment_card_account,
                                                      scheme_account=self.scheme_account)

        resp = self.client.delete(reverse('payment-card', args=[self.payment_card_account.id]),
                                  data="{}",
                                  content_type='application/json', **self.auth_headers)

        self.assertEqual(resp.status_code, 200)

        link = PaymentCardSchemeEntry.objects.filter(pk=entry.pk)
        self.assertEqual(len(link), 1)
    """

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.metis_delete_cards_and_activations", autospec=True)
    def test_payment_card_delete_removes_link_for_cards_not_shared_between_users(self, mock_metis):
        entry = PaymentCardSchemeEntry.objects.create(
            payment_card_account=self.payment_card_account, scheme_account=self.scheme_account
        )

        resp = self.client.delete(
            reverse("payment-card", args=[self.payment_card_account.id]),
            data="{}",
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertTrue(mock_metis.called)
        self.assertEqual(resp.status_code, 200)

        link = PaymentCardSchemeEntry.objects.filter(pk=entry.pk)
        self.assertEqual(len(link), 0)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.metis_delete_cards_and_activations", autospec=True)
    def test_payment_card_delete_by_id(self, _):
        pca = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=self.user, payment_card_account=pca)
        resp = self.client.delete(reverse("payment-card-id", args=[pca.id]), **self.auth_headers)
        pca.refresh_from_db()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(pca.is_deleted)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.metis_delete_cards_and_activations", autospec=True)
    @patch("ubiquity.views.get_secret_key")
    def test_payment_card_delete_by_hash(self, hash_secret, _):
        hash_secret.return_value = "test-secret"
        pca = PaymentCardAccountFactory(hash=BLAKE2sHash().new(obj="testhash", key="test-secret"))
        PaymentCardAccountEntry.objects.create(user=self.user, payment_card_account_id=pca.id)
        resp = self.client.delete(reverse("payment-card-hash", args=["testhash"]), **self.auth_headers)
        pca.refresh_from_db()

        self.assertTrue(hash_secret.called)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(pca.is_deleted)

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_card_rule_filtering(self, *_):
        resp_payment = self.client.get(
            reverse("payment-card", args=[self.payment_card_account.id]), **self.auth_headers
        )
        resp_membership = self.client.get(
            reverse("membership-card", args=[self.scheme_account.id]), **self.auth_headers
        )
        self.assertEqual(resp_payment.status_code, 200)
        self.assertEqual(resp_membership.status_code, 200)

        self.bundle.issuer.add(IssuerFactory())
        self.scheme_bundle_association.status = SchemeBundleAssociation.INACTIVE
        self.scheme_bundle_association.save()

        resp_payment = self.client.get(
            reverse("payment-card", args=[self.payment_card_account.id]), **self.auth_headers
        )
        resp_membership = self.client.get(
            reverse("membership-card", args=[self.scheme_account.id]), **self.auth_headers
        )
        self.assertEqual(resp_payment.status_code, 404)
        self.assertEqual(resp_membership.status_code, 404)

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_card_rule_filtering_suspended(self, *_):
        """
        This test may need revision when ubiquity suspended feature is implemented
        """
        resp_payment = self.client.get(
            reverse("payment-card", args=[self.payment_card_account.id]), **self.auth_headers
        )
        resp_membership = self.client.get(
            reverse("membership-card", args=[self.scheme_account.id]), **self.auth_headers
        )
        self.assertEqual(resp_payment.status_code, 200)
        self.assertEqual(resp_membership.status_code, 200)

        self.bundle.issuer.add(IssuerFactory())
        self.scheme_bundle_association.status = SchemeBundleAssociation.SUSPENDED
        self.scheme_bundle_association.save()

        resp_payment = self.client.get(
            reverse("payment-card", args=[self.payment_card_account.id]), **self.auth_headers
        )
        resp_membership = self.client.get(
            reverse("membership-card", args=[self.scheme_account.id]), **self.auth_headers
        )
        self.assertEqual(resp_payment.status_code, 404)
        self.assertEqual(resp_membership.status_code, 404)

    @patch("payment_card.metis.enrol_new_payment_card")
    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    def test_card_creation_filter(self, *_):
        self.bundle.issuer.add(IssuerFactory())
        self.scheme_bundle_association.status = SchemeBundleAssociation.INACTIVE
        self.scheme_bundle_association.save()
        payload = {
            "card": {
                "last_four_digits": 5234,
                "currency_code": "GBP",
                "first_six_digits": 423456,
                "name_on_card": "test user 2",
                "token": "H7FdKWKPOPhepzxS4MfUuvTDHxr",
                "fingerprint": "b5fe350d5135ab64a8f3c1097fadefd9effb",
                "year": 22,
                "month": 3,
                "order": 1,
            },
            "account": {"consents": [{"timestamp": 1517549941, "type": 0}]},
        }

        resp = self.client.post(
            reverse("payment-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
            **self.version_header,
        )
        self.assertIn("issuer not allowed", resp.json()["detail"])

        payload = {
            "membership_plan": self.scheme.id,
            "account": {"add_fields": [{"column": "barcode", "value": "3038401022657083"}]},
        }
        resp = self.client.post(
            reverse("membership-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
            accept="Application/json;v=1.1",
        )
        self.assertIn("membership plan not allowed", resp.json()["detail"])

    def test_membership_transactions(self):
        expected_resp = [
            {
                "id": 1,
                "status": "active",
                "timestamp": 1589898995,
                "description": "Test Transaction",
                "amounts": [{"currency": "Morgan and Sons", "suffix": "mention-perform", "value": 200}],
            }
        ]
        self.scheme_account.transactions = expected_resp
        self.scheme_account.save(update_fields=["transactions"])
        resp = self.client.get(
            reverse("membership-card-transactions", args=[self.scheme_account.id]), **self.auth_headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertListEqual(resp.json(), expected_resp)

    def test_membership_transactions_invalid_scheme_account(self):
        resp = self.client.get(
            reverse("membership-card-transactions", args=[99999999]), **self.auth_headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_membership_transactions_filters_unauthorised_user(self):
        transactions = [
            {
                "id": 1,
                "status": "active",
                "timestamp": 1589898995,
                "description": "Test Transaction",
                "amounts": [{"currency": "Morgan and Sons", "suffix": "mention-perform", "value": 200}],
            }
        ]
        self.scheme_account.transactions = transactions
        self.scheme_account.save(update_fields=["transactions"])

        # These are the only non-active statuses display_status can currently be set to
        for status in (AccountLinkStatus.PENDING, AccountLinkStatus.JOIN, AccountLinkStatus.WALLET_ONLY):
            self.scheme_account_entry.link_status = status
            self.scheme_account_entry.save(update_fields=["link_status"])

            resp = self.client.get(
                reverse("membership-card-transactions", args=[self.scheme_account.id]), **self.auth_headers
            )
            self.assertEqual(resp.status_code, 200)
            self.assertListEqual(resp.json(), [])

    @httpretty.activate
    def test_user_transactions(self):
        uri = "{}/transactions/user/{}".format(settings.HADES_URL, self.user.id)
        httpretty.register_uri(httpretty.GET, uri, json.dumps(self.test_hades_transactions))
        expected_resp = [
            {
                "id": 1,
                "status": "active",
                "timestamp": 1589898995,
                "description": "Test Transaction",
                "amounts": [{"currency": "Bradford Ltd", "suffix": "behavior-base-than", "value": 200}],
            }
        ]
        resp = self.client.get(reverse("user-transactions"), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["amounts"][0]["value"], 200)
        self.assertTrue(httpretty.has_request())
        self.assertEqual(expected_resp, resp.json())

    @httpretty.activate
    def test_retrieve_transactions(self):
        transaction_id = 1
        uri = "{}/transactions/{}".format(settings.HADES_URL, transaction_id)
        httpretty.register_uri(httpretty.GET, uri, json.dumps(self.test_hades_transactions))
        expected_resp = {
            "id": 1,
            "status": "active",
            "timestamp": 1589898995,
            "description": "Test Transaction",
            "amounts": [{"currency": "Bradford Ltd", "suffix": "behavior-base-than", "value": 200}],
        }
        resp = self.client.get(reverse("retrieve-transactions", args=[transaction_id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(httpretty.has_request())
        self.assertEqual(expected_resp, resp.json())

    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.views.async_balance_with_updated_credentials", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_membership_card_put_missing_membership_plan_error(self, *_):
        sa = SchemeAccountFactory(scheme=self.scheme)
        SchemeAccountEntryFactory(scheme_account=sa, user=self.user)
        payload_put = {
            "account": {
                "add_fields": [{"column": "barcode", "value": "1234401022699099"}],
                "authorise_fields": [{"column": "last_name", "value": "Test Composite"}],
            }
        }
        resp = self.client.put(
            reverse("membership-card", args=[sa.id]),
            data=json.dumps(payload_put),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json(), {"detail": "required field membership_plan is missing"})

    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.views.async_balance_with_updated_credentials", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_membership_card_put_manual_question_single_link(self, *_):
        """
        Tests that a PUT with a different, non-existing add_field (manual_question_answer) results in a new account
        being created, the schemeaccountentry switched to the new account, and the old account deleted.
        (Single link/LastManStanding)
        """
        scheme_account = SchemeAccountFactory(scheme=self.put_scheme, card_number="55555")
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)
        SchemeCredentialAnswerFactory(
            question=self.put_scheme_manual_q,
            answer="55555",
            scheme_account_entry=scheme_account_entry,
        )
        SchemeCredentialAnswerFactory(
            question=self.put_scheme_auth_q,
            answer="pass",
            scheme_account_entry=scheme_account_entry,
        )

        payload = {
            "membership_plan": self.put_scheme.id,
            "account": {
                "add_fields": [{"column": "card_number", "value": "12345"}],
                "authorise_fields": [{"column": "password", "value": "pass"}],
            },
        }

        resp_put = self.client.put(
            reverse("membership-card", args=[scheme_account.id]),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
        )

        scheme_account.refresh_from_db()
        scheme_account_entry.refresh_from_db()

        new_scheme_acc_id = resp_put.data["id"]
        new_scheme_acc = SchemeAccount.objects.get(id=new_scheme_acc_id)
        new_scheme_acc_entry = SchemeAccountEntry.objects.get(scheme_account=new_scheme_acc, user=self.user)

        self.assertEqual(resp_put.status_code, 200)

        self.assertTrue(scheme_account.is_deleted)
        self.assertEqual(scheme_account_entry.scheme_account, new_scheme_acc)

        answers = scheme_account_entry._collect_credential_answers()
        new_manual_answer = answers.get(self.put_scheme_manual_q.type)
        self.assertEqual(new_manual_answer, "12345")
        self.assertIsNone(answers.get(self.put_scheme_scan_q.type))

        self.assertEqual(new_scheme_acc.card_number, "12345")
        self.assertEqual(new_scheme_acc_entry.link_status, AccountLinkStatus.PENDING)

    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.views.async_balance_with_updated_credentials", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_membership_card_put_different_nonexisting_manual_question_multiple_links(self, *_):
        """
        Tests that a PUT with a different, non-existing add_field (manual_question_answer) results in a new account
        being created, the schemeaccountentry switched to the new account, and the old account unaffected.
        (Multiple link/ NOT LastManStanding)
        """
        scheme_account = SchemeAccountFactory(scheme=self.put_scheme, card_number="55555")
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=self.user, link_status=AccountLinkStatus.ACTIVE
        )
        scheme_account_entry_2 = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=self.user2, link_status=AccountLinkStatus.ACTIVE
        )
        SchemeCredentialAnswerFactory(
            question=self.put_scheme_manual_q,
            answer="55555",
            scheme_account_entry=scheme_account_entry,
        )
        SchemeCredentialAnswerFactory(
            question=self.put_scheme_auth_q,
            answer="pass",
            scheme_account_entry=scheme_account_entry,
        )

        payload = {
            "membership_plan": self.put_scheme.id,
            "account": {
                "add_fields": [{"column": "card_number", "value": "12345"}],
                "authorise_fields": [{"column": "password", "value": "pass"}],
            },
        }

        resp_put = self.client.put(
            reverse("membership-card", args=[scheme_account.id]),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
        )

        scheme_account.refresh_from_db()
        scheme_account_entry.refresh_from_db()

        new_scheme_acc_id = resp_put.data["id"]
        new_scheme_acc = SchemeAccount.objects.get(id=new_scheme_acc_id)

        self.assertEqual(resp_put.status_code, 200)

        self.assertFalse(scheme_account.is_deleted)
        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.PENDING)
        self.assertEqual(scheme_account_entry.scheme_account, new_scheme_acc)
        self.assertEqual(scheme_account_entry_2.link_status, AccountLinkStatus.ACTIVE)
        self.assertEqual(scheme_account_entry_2.scheme_account, scheme_account)

        answers = scheme_account_entry._collect_credential_answers()
        new_manual_answer = answers.get(self.put_scheme_manual_q.type)
        self.assertEqual(new_manual_answer, "12345")
        self.assertIsNone(answers.get(self.put_scheme_scan_q.type))

        self.assertEqual(new_scheme_acc.card_number, "12345")

    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.views.async_balance_with_updated_credentials", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_membership_card_put_scan_question_single_link(self, *_):
        """
        Tests that a PUT with a different, non-existing add_field (scan_question_answer) results in a new account
        being created, the schemeaccountentry switched to the new account, and the old account deleted.
        (Single link/LastManStanding)
        """
        scheme_account = SchemeAccountFactory(scheme=self.put_scheme)
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)
        SchemeCredentialAnswerFactory(
            question=self.put_scheme_manual_q,
            answer="55555",
            scheme_account_entry=scheme_account_entry,
        )
        SchemeCredentialAnswerFactory(
            question=self.put_scheme_auth_q,
            answer="pass",
            scheme_account_entry=scheme_account_entry,
        )

        payload = {
            "membership_plan": self.put_scheme.id,
            "account": {
                "add_fields": [{"column": "barcode", "value": "67890"}],
                "authorise_fields": [{"column": "password", "value": "pass"}],
            },
        }

        resp_put = self.client.put(
            reverse("membership-card", args=[scheme_account.id]),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
        )

        scheme_account.refresh_from_db()
        scheme_account_entry.refresh_from_db()

        new_scheme_acc = SchemeAccount.objects.get(id=resp_put.data["id"])
        new_scheme_acc_entry = SchemeAccountEntry.objects.get(scheme_account=new_scheme_acc, user=self.user)

        self.assertEqual(resp_put.status_code, 200)

        self.assertTrue(scheme_account.is_deleted)

        self.assertEqual(scheme_account_entry.scheme_account, new_scheme_acc)
        self.assertEqual(new_scheme_acc_entry.link_status, AccountLinkStatus.PENDING)
        self.assertEqual(new_scheme_acc.barcode, "67890")

        answers = scheme_account_entry._collect_credential_answers()
        new_scan_answer = answers.get(self.put_scheme_scan_q.type)
        self.assertEqual(new_scan_answer, "67890")

    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.views.async_balance_with_updated_credentials", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_membership_card_put_with_previous_balance(self, *_):
        """
        Tests that a PUT with a different, non-existing add_field (scan_question_answer) results in a new account
        being created, and that no balance is present on this new card.
        (Single link/LastManStanding)
        """
        scheme_account = SchemeAccountFactory(scheme=self.put_scheme)
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)
        SchemeCredentialAnswerFactory(
            question=self.put_scheme_manual_q,
            answer="9999",
            scheme_account_entry=scheme_account_entry,
        )
        SchemeCredentialAnswerFactory(
            question=self.put_scheme_auth_q,
            answer="pass",
            scheme_account_entry=scheme_account_entry,
        )
        scheme_account.balances = [{"points": 1, "scheme_account_id": 27308}]
        scheme_account.save()

        payload = {
            "membership_plan": self.put_scheme.id,
            "account": {
                "add_fields": [{"column": "card_number", "value": "12345"}],
                "authorise_fields": [{"column": "password", "value": "pass"}],
            },
        }

        resp_put = self.client.put(
            reverse("membership-card", args=[scheme_account.id]),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
        )

        scheme_account.refresh_from_db()

        new_scheme_acc = SchemeAccount.objects.get(id=resp_put.data["id"])
        new_scheme_acc_entry = SchemeAccountEntry.objects.get(scheme_account=new_scheme_acc, user=self.user)

        self.assertEqual(resp_put.status_code, 200)
        self.assertEqual(new_scheme_acc_entry.link_status, AccountLinkStatus.PENDING)
        self.assertFalse(new_scheme_acc.balances)

    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.views.async_balance_with_updated_credentials", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_membership_card_put_on_pending_card_error(self, *_):
        scheme_account = SchemeAccountFactory(scheme=self.put_scheme)
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=self.user, link_status=AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS
        )
        test_card_no = "654321"
        test_pass = "pass4"
        SchemeCredentialAnswerFactory(
            question=self.put_scheme_manual_q,
            answer=test_card_no,
            scheme_account_entry=scheme_account_entry,
        )
        SchemeCredentialAnswerFactory(
            question=self.put_scheme_auth_q,
            answer=test_pass,
            scheme_account_entry=scheme_account_entry,
        )

        payload = {
            "membership_plan": self.put_scheme.id,
            "account": {
                "add_fields": [{"column": CARD_NUMBER, "value": "67890"}],
                "authorise_fields": [{"column": PASSWORD, "value": "pass"}],
            },
        }

        resp = self.client.put(
            reverse("membership-card", args=[scheme_account.id]),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(resp.status_code, 400)
        error_message = resp.json().get("detail")
        self.assertEqual(
            error_message, "requested card is still in a pending state, please wait for " "current journey to finish"
        )

        scheme_account.refresh_from_db()
        answers = scheme_account_entry._collect_credential_answers()
        add_answer = answers.get(self.put_scheme_manual_q.type)
        auth_answer = answers.get(self.put_scheme_auth_q.type)
        self.assertEqual(add_answer, test_card_no)
        self.assertEqual(auth_answer, test_pass)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch.object(SchemeAccount, "update_cached_balance", autospec=True, return_value=(10, "", None))
    @patch("ubiquity.tasks.async_balance", autospec=True)
    @patch("ubiquity.views.async_registration", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_membership_card_patch(self, *_):
        external_id = "test patch user 1"
        user = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        auth_headers = {"HTTP_AUTHORIZATION": "{}".format(self._get_auth_header(user))}
        sa = SchemeAccountFactory(scheme=self.scheme, card_number="12345", originating_journey=JourneyTypes.ADD)
        scheme_account_entry = SchemeAccountEntryFactory(
            user=user, scheme_account=sa, link_status=AccountLinkStatus.ACTIVE
        )
        SchemeCredentialAnswerFactory(
            question=self.scheme.manual_question,
            answer="12345",
            scheme_account_entry=scheme_account_entry,
        )
        SchemeCredentialAnswerFactory(
            question=self.secondary_question,
            answer="name",
            scheme_account_entry=scheme_account_entry,
        )
        expected_value = {"last_name": "changed name"}
        payload_update = {"account": {"authorise_fields": [{"column": "last_name", "value": "changed name"}]}}
        resp_update = self.client.patch(
            reverse("membership-card", args=[sa.id]),
            data=json.dumps(payload_update),
            content_type="application/json",
            **auth_headers,
        )
        self.assertEqual(resp_update.status_code, 200)
        scheme_account_entry.refresh_from_db()
        scheme_account_entry.link_status = AccountLinkStatus.PRE_REGISTERED_CARD
        scheme_account_entry.save()
        sa.save()
        sa.refresh_from_db()

        self.assertEqual(expected_value["last_name"], scheme_account_entry._collect_credential_answers()["last_name"])

        payload_register = {"account": {"registration_fields": [{"column": "last_name", "value": "new changed name"}]}}
        resp_register = self.client.patch(
            reverse("membership-card", args=[sa.id]),
            data=json.dumps(payload_register),
            content_type="application/json",
            **auth_headers,
        )
        self.assertEqual(resp_register.status_code, 200)
        sa.refresh_from_db()
        scheme_account_entry.refresh_from_db()
        self.assertIn(scheme_account_entry.link_status, AccountLinkStatus.register_pending())
        self.assertEqual(sa.originating_journey, JourneyTypes.ADD)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch.object(SchemeAccount, "update_cached_balance", autospec=True, return_value=(10, "", None))
    @patch("ubiquity.tasks.async_balance", autospec=True)
    @patch("ubiquity.views.async_registration", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_check_patch_does_not_override_originating_journey(self, *_):
        external_id = "test patch user 1"
        user = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        auth_headers = {"HTTP_AUTHORIZATION": "{}".format(self._get_auth_header(user))}
        sa = SchemeAccountFactory(scheme=self.scheme, card_number="12345", originating_journey=JourneyTypes.JOIN)
        scheme_account_entry = SchemeAccountEntryFactory(user=user, scheme_account=sa)
        SchemeCredentialAnswerFactory(
            question=self.scheme.manual_question,
            answer="12345",
            scheme_account_entry=scheme_account_entry,
        )
        SchemeCredentialAnswerFactory(
            question=self.secondary_question,
            answer="name",
            scheme_account_entry=scheme_account_entry,
        )
        expected_value = {"last_name": "changed name"}
        payload_update = {"account": {"authorise_fields": [{"column": "last_name", "value": "changed name"}]}}
        resp_update = self.client.patch(
            reverse("membership-card", args=[sa.id]),
            data=json.dumps(payload_update),
            content_type="application/json",
            **auth_headers,
        )
        self.assertEqual(resp_update.status_code, 200)
        scheme_account_entry.link_status = AccountLinkStatus.PRE_REGISTERED_CARD
        sa.save()
        sa.refresh_from_db()
        self.assertEqual(expected_value["last_name"], scheme_account_entry._collect_credential_answers()["last_name"])

        payload_register = {"account": {"registration_fields": [{"column": "last_name", "value": "new changed name"}]}}
        resp_register = self.client.patch(
            reverse("membership-card", args=[sa.id]),
            data=json.dumps(payload_register),
            content_type="application/json",
            **auth_headers,
        )
        self.assertEqual(resp_register.status_code, 200)
        sa.refresh_from_db()
        self.assertEqual(sa.originating_journey, JourneyTypes.JOIN)

    @patch("ubiquity.cache_decorators.ApiCache", new=MockApiCache)
    def test_membership_plans(self):
        MockApiCache.available_called = False
        MockApiCache.expire = 0
        resp = self.client.get(reverse("membership-plans"), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(isinstance(resp.json(), list))
        self.assertTrue(MockApiCache.available_called)
        self.assertEqual(MockApiCache.key, "m_plans:test.auth.fake:0:1.3")
        self.assertEqual(MockApiCache.expire, 60 * 60 * 24)
        self.assertListEqual(MockApiCache.data, resp.json())

        schemes_number = len(resp.json())

        self.scheme_bundle_association.test_scheme = True
        self.scheme_bundle_association.status = SchemeBundleAssociation.ACTIVE
        self.scheme_bundle_association.save()
        resp = self.client.get(reverse("membership-plans"), **self.auth_headers)
        self.assertLess(len(resp.json()), schemes_number)

        self.user.is_tester = True
        self.user.save()
        resp = self.client.get(reverse("membership-plans"), **self.auth_headers)
        self.assertEqual(len(resp.json()), schemes_number)

        self.scheme_bundle_association.test_scheme = False
        self.scheme_bundle_association.save()
        self.user.is_tester = False
        self.user.save()

    @patch("ubiquity.cache_decorators.ApiCache", new=MockApiCache)
    def test_membership_plan(self):
        mock_request_context = MagicMock()
        mock_request_context.user = self.user
        MockApiCache.available_called = False
        MockApiCache.expire = 0
        resp = self.client.get(reverse("membership-plan", args=[self.scheme.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(MockApiCache.available_called)
        self.assertEqual(MockApiCache.key, f"m_plans:{self.scheme.id}:test.auth.fake:0:1.3")
        self.assertEqual(MockApiCache.expire, 60 * 60 * 24)
        self.assertDictEqual(MockApiCache.data, resp.json())

        resp = self.client.get(
            reverse("membership-plan", args=[self.scheme.id]), **self.auth_headers, **self.version_header_v1_2
        )
        self.assertEqual(
            remove_empty(MembershipPlanSerializer(self.scheme, context={"request": mock_request_context}).data),
            resp.json(),
        )

        self.scheme_bundle_association.test_scheme = True
        self.scheme_bundle_association.status = SchemeBundleAssociation.ACTIVE
        self.scheme_bundle_association.save()

        resp = self.client.get(reverse("membership-plan", args=[self.scheme.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 404)

        self.user.is_tester = True
        self.user.save()
        resp = self.client.get(reverse("membership-plan", args=[self.scheme.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

        self.scheme_bundle_association.test_scheme = False
        self.scheme_bundle_association.save()
        self.user.is_tester = False
        self.user.save()

    def test_composite_membership_plan(self):
        mock_request_context = MagicMock()
        mock_request_context.user = self.user

        expected_result = remove_empty(
            MembershipPlanSerializer(self.scheme_account.scheme, context={"request": mock_request_context}).data
        )
        resp = self.client.get(
            reverse("membership-card-plan", args=[self.scheme_account.id]),
            **self.auth_headers,
            **self.version_header_v1_2,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    @patch.object(SchemeAccount, "get_midas_balance")
    def test_membership_card_balance(self, mock_get_midas_balance, *_):
        mock_get_midas_balance.return_value = (
            {
                "value": Decimal("10"),
                "points": Decimal("100"),
                "points_label": "100",
                "value_label": "$10",
                "reward_tier": 0,
                "balance": Decimal("20"),
                "is_stale": False,
            },
            (True, AccountLinkStatus.PENDING),
        )

        expected_keys = {"value", "currency", "updated_at"}
        self.scheme_account.get_cached_balance(self.scheme_account_entry)
        resp = self.client.get(reverse("membership-card", args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["balances"][0]["value"], 100)
        self.assertTrue(expected_keys.issubset(set(resp.json()["balances"][0].keys())))

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    @patch.object(SchemeAccount, "get_midas_balance")
    def test_get_cached_balance_link(self, mock_get_midas_balance, *_):
        test_scheme_account = SchemeAccountFactory(scheme=self.scheme)
        mock_get_midas_balance.return_value = (
            {
                "value": Decimal("10"),
                "points": Decimal("100"),
                "points_label": "100",
                "value_label": "$10",
                "reward_tier": 0,
                "balance": Decimal("20"),
                "is_stale": False,
            },
            (True, AccountLinkStatus.PENDING),
        )

        self.assertFalse(test_scheme_account.balances)
        test_scheme_account.get_cached_balance(self.scheme_account_entry)
        self.assertTrue(mock_get_midas_balance.called)
        self.assertEqual(mock_get_midas_balance.call_args[1]["journey"], JourneyTypes.LINK)
        self.assertTrue(test_scheme_account.balances)

        test_scheme_account.get_cached_balance(self.scheme_account_entry)
        self.assertEqual(mock_get_midas_balance.call_args[1]["journey"], JourneyTypes.UPDATE)

    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_existing_membership_card_creation_success(self, *_):
        new_external_id = "Test User mcard creation success"
        new_user = UserFactory(external_id=new_external_id, client=self.client_app, email=new_external_id)

        # Test for schemes with additional non user credentials
        merch_identifier = SchemeCredentialQuestionFactory(
            scheme=self.scheme,
            type=MERCHANT_IDENTIFIER,
            label=MERCHANT_IDENTIFIER,
            options=SchemeCredentialQuestion.MERCHANT_IDENTIFIER,
        )

        new_answer = SchemeCredentialAnswerFactory(
            question=merch_identifier,
            scheme_account_entry=self.scheme_account_entry,
        )

        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [{"column": "barcode", "value": self.scheme_account.barcode}],
                "authorise_fields": [{"column": "last_name", "value": self.second_scheme_account_answer.answer}],
            },
        }

        auth_header = self._get_auth_header(new_user)
        resp = self.client.post(
            reverse("membership-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=auth_header,
        )

        self.assertEqual(resp.status_code, 200)

        linked = SchemeAccountEntry.objects.filter(user=new_user, scheme_account=self.scheme_account).exists()
        self.assertTrue(linked)

        # remove additional question/answer from test scheme
        new_answer.delete()
        merch_identifier.delete()

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch.object(SchemeAccount, "get_midas_balance")
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_credential_emails_are_stored_as_lowercase_auth_route(self, *_):
        new_user, scheme, card_num_question, email_question, auth_header = self._setup_user_and_email_scheme()

        # Test for auth route
        email = "MiXedCaSe@EmAiL.COm"

        payload = {
            "membership_plan": scheme.id,
            "account": {
                "add_fields": [{"column": CARD_NUMBER, "value": "123456789"}],
                "authorise_fields": [{"column": EMAIL, "value": email}],
            },
        }

        resp = self.client.post(
            reverse("membership-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=auth_header,
        )

        self.assertEqual(resp.status_code, 201)

        scheme_acc_id = resp.json()["id"]
        linked = SchemeAccountEntry.objects.filter(user=new_user, scheme_account_id=scheme_acc_id).exists()
        self.assertTrue(linked)

        answers = SchemeAccountCredentialAnswer.objects.filter(
            scheme_account_entry__scheme_account_id=scheme_acc_id, question=email_question
        )
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0].answer, "mixedcase@email.com")

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    @patch("api_messaging.midas_messaging.to_midas", autospec=True, return_value=MagicMock())
    def test_credential_emails_are_stored_as_lowercase_enrol_route(self, mock_join_msg, *_):
        new_user, scheme, card_num_question, email_question, auth_header = self._setup_user_and_email_scheme()

        email = "MiXedCaSe@EmAiL.COm"
        payload = {"membership_plan": scheme.id, "account": {"enrol_fields": [{"column": EMAIL, "value": email}]}}

        resp = self.client.post(
            reverse("membership-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=auth_header,
        )

        self.assertEqual(resp.status_code, 201)

        scheme_acc_id = resp.json()["id"]
        linked = SchemeAccountEntry.objects.filter(user=new_user, scheme_account_id=scheme_acc_id).exists()
        self.assertTrue(linked)

        answers = SchemeAccountCredentialAnswer.objects.filter(
            scheme_account_entry__scheme_account_id=scheme_acc_id, question=email_question
        )
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0].answer, "mixedcase@email.com")
        self.assertTrue(mock_join_msg.called)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch.object(SchemeAccount, "get_midas_balance")
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    @patch("api_messaging.midas_messaging.to_midas", autospec=True, return_value=MagicMock())
    def test_credential_emails_are_stored_as_lowercase_register_route(self, mock_join_msg, *_):
        new_user, scheme, card_num_question, email_question, auth_header = self._setup_user_and_email_scheme()
        card_number = "123456789"
        scheme_account = SchemeAccountFactory(scheme=scheme)
        scheme_account.card_number = card_number
        scheme_account.save(update_fields=["card_number"])
        scheme_account_entry = SchemeAccountEntryFactory(user=new_user, scheme_account=scheme_account)

        SchemeCredentialAnswerFactory(
            question=scheme.manual_question,
            answer=card_number,
            scheme_account_entry=scheme_account_entry,
        )

        email = "MiXedCaSe@EmAiL.COm"
        payload = {
            "membership_plan": scheme.id,
            "account": {
                "add_fields": [{"column": CARD_NUMBER, "value": card_number}],
                "registration_fields": [{"column": EMAIL, "value": email}],
            },
        }

        resp = self.client.patch(
            reverse("membership-card", args=[scheme_account.id]),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=auth_header,
        )

        self.assertEqual(resp.status_code, 200)

        answers = SchemeAccountCredentialAnswer.objects.filter(
            scheme_account_entry__scheme_account_id=scheme_account.id, question=email_question
        )
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0].answer, "mixedcase@email.com")
        self.assertTrue(mock_join_msg.called)

    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_existing_membership_card_creation_postcode_space_handling(self, *_):
        # Setup new scheme with all question types as auth fields and create existing scheme account
        new_external_id = "Test User non case sensitive auth fields"
        new_user = UserFactory(external_id=new_external_id, client=self.client_app, email=new_external_id)
        auth_header = self._get_auth_header(new_user)
        scheme = SchemeFactory()
        scheme_account = SchemeAccountFactory(scheme=scheme)
        scheme_account.alt_main_answer = fake.email()
        scheme_account.save(update_fields=["alt_main_answer"])
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account)
        SchemeBundleAssociationFactory(scheme=scheme, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE)
        SchemeCredentialQuestionFactory(
            scheme=scheme, type=EMAIL, label=EMAIL, manual_question=True, add_field=True, enrol_field=True
        )
        email = SchemeCredentialAnswerFactory(
            question=scheme.manual_question,
            answer=scheme_account.alt_main_answer,
            scheme_account_entry=scheme_account_entry,
        )
        scheme_account_entry.update_scheme_account_key_credential_fields()

        postcode_question = SchemeCredentialQuestionFactory(
            scheme=scheme,
            type=POSTCODE,
            label=POSTCODE,
            third_party_identifier=False,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            auth_field=True,
            enrol_field=True,
            register_field=True,
        )
        test_postcode = "CR0 1FB"
        SchemeCredentialAnswerFactory(
            question=postcode_question,
            answer=test_postcode,
            scheme_account_entry=scheme_account_entry,
        )

        payload = {
            "membership_plan": scheme.id,
            "account": {
                "add_fields": [{"column": EMAIL, "value": email.answer}],
                "authorise_fields": [{"column": POSTCODE, "value": test_postcode}],
            },
        }

        # Test adding card without spaces
        payload["account"]["authorise_fields"] = [{"column": POSTCODE, "value": test_postcode.replace(" ", "")}]

        resp = self.client.post(
            reverse("membership-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=auth_header,
        )
        self.assertEqual(resp.status_code, 200)
        link = SchemeAccountEntry.objects.filter(user=new_user, scheme_account=scheme_account)
        self.assertTrue(link.exists())
        link.delete()

        # Test adding card with multiple whitespace characters
        payload["account"]["authorise_fields"] = [{"column": POSTCODE, "value": "\n CR0\r  1FB\n\t"}]

        resp = self.client.post(
            reverse("membership-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=auth_header,
        )
        self.assertEqual(resp.status_code, 200)
        link = SchemeAccountEntry.objects.filter(user=new_user, scheme_account=scheme_account)
        self.assertTrue(link.exists())

    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_existing_membership_card_creation_non_matching_question_type(self, mock_analytics, *_):
        mock_analytics._get_today_datetime.return_value = datetime.datetime(year=2000, month=5, day=19)
        payload = {
            "membership_plan": self.scheme.id,
            "account": {"authorise_fields": [{"column": "barcode", "value": self.scheme_account.barcode}]},
        }
        new_external_id = "Test User 2"
        new_user = UserFactory(external_id=new_external_id, client=self.client_app, email=new_external_id)
        PaymentCardAccountEntryFactory(user=new_user, payment_card_account=self.payment_card_account)
        auth_header = self._get_auth_header(new_user)
        resp = self.client.post(
            reverse("membership-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=auth_header,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Column does not match field type.", resp.json())

    def test_membership_plan_serializer_method(self):
        serializer = MembershipPlanSerializer()
        test_dict = [{"column": 1}, {"column": 2}, {"column": 3}]
        expected = [
            {"column": 1, "alternatives": [2, 3]},
            {"column": 2, "alternatives": [1, 3]},
            {"column": 3, "alternatives": [1, 2]},
        ]
        serializer._add_alternatives_key(test_dict)
        self.assertEqual(expected, test_dict)

    @patch("ubiquity.views.async_all_balance.delay")
    def test_get_service(self, mock_async_all_balance):
        resp = self.client.get(reverse("service"), **self.auth_headers)
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(mock_async_all_balance.called)

        ServiceConsentFactory(user=self.user)
        resp = self.client.get(reverse("service"), **self.auth_headers)

        self.assertEqual(resp.status_code, 200)
        self.assertIn("consent", resp.data.keys())
        self.assertTrue(mock_async_all_balance.called)
        self.assertEqual(mock_async_all_balance.call_args[0][0], self.user.id)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("ubiquity.tasks.remove_loyalty_card_event")
    @patch("ubiquity.tasks.metis", autospec=True)
    def test_delete_service(self, _, mock_to_warehouse):
        user = UserFactory(external_id="test@delete.user", client=self.client_app, email="test@delete.user")
        ServiceConsentFactory(user=user)
        pcard_delete = PaymentCardAccountFactory()
        pcard_unlink = PaymentCardAccountFactory()
        mcard_delete = SchemeAccountFactory()
        mcard_unlink = SchemeAccountFactory()
        auth_headers = {"HTTP_AUTHORIZATION": "{}".format(self._get_auth_header(user))}

        PaymentCardAccountEntry.objects.create(user_id=user.id, payment_card_account_id=pcard_delete.id)
        PaymentCardAccountEntry.objects.create(user_id=user.id, payment_card_account_id=pcard_unlink.id)
        PaymentCardAccountEntry.objects.create(user_id=self.user.id, payment_card_account_id=pcard_unlink.id)

        SchemeAccountEntry.objects.create(user_id=user.id, scheme_account_id=mcard_delete.id)
        SchemeAccountEntry.objects.create(user_id=user.id, scheme_account_id=mcard_unlink.id)
        SchemeAccountEntry.objects.create(user_id=self.user.id, scheme_account_id=mcard_unlink.id)

        response = self.client.delete(reverse("service"), **auth_headers)
        self.assertEqual(response.status_code, 200)

        pcard_unlink.refresh_from_db()
        pcard_delete.refresh_from_db()
        mcard_unlink.refresh_from_db()
        mcard_delete.refresh_from_db()
        user.refresh_from_db()

        self.assertTrue(pcard_delete.is_deleted)
        self.assertTrue(mcard_delete.is_deleted)
        self.assertFalse(pcard_unlink.is_deleted)
        self.assertFalse(mcard_unlink.is_deleted)
        self.assertNotEquals(user.delete_token, "")

        non_deleted_links = SchemeAccountEntry.objects.filter(user_id=user.id).count()
        self.assertEqual(non_deleted_links, 0)

        self.assertTrue(mock_to_warehouse.called)
        self.assertEqual(mock_to_warehouse.call_count, 2)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch.object(BaseLinkMixin, "link_account", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_auto_link(self, *_):
        external_id = "test auto link"
        user = UserFactory(external_id=external_id, client=self.client_app, email=external_id)

        auth_header = self._get_auth_header(user)
        auth_headers = {"HTTP_AUTHORIZATION": "{}".format(auth_header)}
        payment_card_account = PaymentCardAccountFactory(issuer=self.issuer, payment_card=self.payment_card)
        PaymentCardAccountEntryFactory(user=user, payment_card_account=payment_card_account)
        query = {"payment_card_account_id": payment_card_account.id}

        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [{"column": "barcode", "value": "123456789"}],
                "authorise_fields": [{"column": "last_name", "value": "Test Successful Link"}],
            },
        }
        success_resp = self.client.post(
            f'{reverse("membership-cards")}?autoLink=True',
            data=json.dumps(payload),
            content_type="application/json",
            **auth_headers,
        )

        self.assertEqual(success_resp.status_code, 201)
        query["scheme_account_id"] = success_resp.json()["id"]

        self.assertTrue(PaymentCardSchemeEntry.objects.filter(**query).exists())

        # linking a second loyalty card of the same plan to the same payment account. UBIQUITY_COLLISION scenario.
        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [{"column": "barcode", "value": "987654321"}],
                "authorise_fields": [{"column": "last_name", "value": "Test Excluded Link"}],
            },
        }
        fail_resp = self.client.post(
            f'{reverse("membership-cards")}?autoLink=True',
            data=json.dumps(payload),
            content_type="application/json",
            **auth_headers,
        )

        self.assertEqual(fail_resp.status_code, 201)
        entries = (
            PaymentCardSchemeEntry.objects.filter(
                payment_card_account=payment_card_account, scheme_account__scheme=self.scheme
            )
            .order_by("id")
            .all()
        )
        self.assertEqual(len(entries), 2)
        ulinks = PllUserAssociation.objects.get(pll=entries[1], user=user)
        self.assertEqual(ulinks.slug, WalletPLLSlug.UBIQUITY_COLLISION.value)
        self.assertEqual(ulinks.state, WalletPLLStatus.INACTIVE.value)
        self.assertFalse(entries[1].active_link)

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.views.async_join", autospec=True)
    @patch("payment_card.payment.get_secret_key", autospec=True)
    def test_replace_mcard_with_enrol_fields(self, mock_secret, mock_async_join, mock_async_balance):
        mock_secret.return_value = "test_secret"
        self.scheme_account_entry.link_status = AccountLinkStatus.ENROL_FAILED
        self.scheme_account_entry.save(update_fields=["link_status"])

        consent_label = "Consent 1"
        consent = ConsentFactory.create(scheme=self.scheme, journey=JourneyTypes.JOIN.value)

        ThirdPartyConsentLink.objects.create(
            consent_label=consent_label,
            client_app=self.client_app,
            scheme=self.scheme,
            consent=consent,
            add_field=False,
            auth_field=False,
            register_field=True,
            enrol_field=True,
        )

        payload = {
            "account": {
                "enrol_fields": [
                    {"column": LAST_NAME, "value": "New last name"},
                    {"column": PAYMENT_CARD_HASH, "value": self.pcard_hash1},
                    {"column": consent_label, "value": "True"},
                ]
            },
            "membership_plan": self.scheme_account.scheme_id,
        }

        resp = self.client.put(
            reverse("membership-card", args=[self.scheme_account.id]),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
            **self.version_header,
        )

        self.assertEqual(resp.status_code, 200)
        self.scheme_account.refresh_from_db()
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS)
        self.assertIn(self.scheme_account_entry.link_status, AccountLinkStatus.join_pending())
        self.assertTrue(not self.scheme_account_entry.schemeaccountcredentialanswer_set.all())
        self.assertTrue(mock_async_join.delay.called)
        self.assertTrue(mock_async_balance.delay.called)

    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch("ubiquity.views.async_join", autospec=True)
    @patch("payment_card.payment.get_secret_key", autospec=True)
    def test_replace_mcard_with_enrol_fields_including_main_answer(
        self, mock_secret, mock_async_join, mock_async_balance
    ):
        mock_secret.return_value = "test_secret"
        self.scheme_account_entry.status = AccountLinkStatus.ENROL_FAILED
        self.scheme_account_entry.save(update_fields=["link_status"])

        consent_label = "Consent 1"
        consent = ConsentFactory.create(scheme=self.scheme, journey=JourneyTypes.JOIN.value)

        ThirdPartyConsentLink.objects.create(
            consent_label=consent_label,
            client_app=self.client_app,
            scheme=self.scheme,
            consent=consent,
            add_field=False,
            auth_field=False,
            register_field=True,
            enrol_field=True,
        )

        main_answer = "1111111111111111111"

        payload = {
            "account": {
                "enrol_fields": [
                    {"column": BARCODE, "value": main_answer},
                    {"column": LAST_NAME, "value": "New last name"},
                    {"column": PAYMENT_CARD_HASH, "value": self.pcard_hash1},
                    {"column": consent_label, "value": "True"},
                ]
            },
            "membership_plan": self.scheme_account.scheme_id,
        }

        resp = self.client.put(
            reverse("membership-card", args=[self.scheme_account.id]),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
            **self.version_header,
        )

        self.assertEqual(resp.status_code, 200)
        self.scheme_account.refresh_from_db()
        self.scheme_account_entry.refresh_from_db()
        self.assertEqual(self.scheme_account.alt_main_answer, main_answer)
        self.assertEqual(self.scheme_account_entry.link_status, AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS)
        self.assertTrue(not self.scheme_account_entry.schemeaccountcredentialanswer_set.all())
        self.assertTrue(mock_async_join.delay.called)
        self.assertTrue(mock_async_balance.delay.called)


class TestAgainWithWeb2(TestResources):
    @classmethod
    def _get_auth_header(cls, user):
        token = user.create_token()
        return "Token {}".format(token)


class TestMembershipCardCredentials(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        organisation = OrganisationFactory(name="set up authentication for credentials")
        client = ClientApplicationFactory(organisation=organisation, name="set up credentials application")
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.credentials.fake", client=client)
        external_id = "credentials@user.com"
        cls.user = UserFactory(external_id=external_id, client=client, email=external_id)
        cls.scheme = SchemeFactory()
        cls.scheme_bundle_association = SchemeBundleAssociationFactory(
            scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )
        SchemeBalanceDetailsFactory(scheme_id=cls.scheme)
        SchemeCredentialQuestionFactory(
            scheme=cls.scheme, type=BARCODE, label=BARCODE, manual_question=True, add_field=True
        )
        SchemeCredentialQuestionFactory(scheme=cls.scheme, type=PASSWORD, label=PASSWORD, auth_field=True)
        secondary_question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme,
            type=LAST_NAME,
            label=LAST_NAME,
            third_party_identifier=True,
            options=SchemeCredentialQuestion.LINK,
            auth_field=True,
        )
        cls.scheme_account = SchemeAccountFactory(scheme=cls.scheme)
        cls.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=cls.scheme_account, user=cls.user)
        cls.scheme_account_answer = SchemeCredentialAnswerFactory(
            question=cls.scheme.manual_question,
            scheme_account_entry=cls.scheme_account_entry,
        )
        cls.second_scheme_account_answer = SchemeCredentialAnswerFactory(
            question=secondary_question,
            scheme_account_entry=cls.scheme_account_entry,
        )
        token = GenerateJWToken(client.organisation.name, client.secret, cls.bundle.bundle_id, external_id).get_token()
        cls.auth_headers = {"HTTP_AUTHORIZATION": "Bearer {}".format(token)}

    @patch("ubiquity.views.async_balance_with_updated_credentials.delay", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    @patch.object(SchemeAccount, "get_midas_balance")
    def test_update_new_and_existing_credentials(self, *_):
        payload = {
            "account": {
                "authorise_fields": [
                    {"column": "last_name", "value": "New Last Name"},
                    {"column": "password", "value": "newpassword"},
                ]
            }
        }
        resp = self.client.patch(
            reverse("membership-card", args=[self.scheme_account.id]),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)


class TestResourcesV1_2(GlobalMockAPITestCase):
    @classmethod
    def _get_auth_header(cls, user):
        token = GenerateJWToken(
            cls.client_app.organisation.name, cls.client_app.secret, cls.bundle.bundle_id, user.external_id
        ).get_token()
        return "Bearer {}".format(token)

    @classmethod
    def setUpTestData(cls) -> None:
        cls.rsa = RSACipher()
        cls.bundle_id = "com.barclays.test"
        cls.pub_key = mock_secrets["bundle_secrets"][cls.bundle_id]["public_key"]

        organisation = OrganisationFactory(name="test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=organisation,
            name="set up client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id=cls.bundle_id, client=cls.client_app)
        cls.scheme = SchemeFactory()

        cls.question_1 = SchemeCredentialQuestionFactory(
            scheme=cls.scheme,
            answer_type=AnswerTypeChoices.SENSITIVE.value,
            auth_field=True,
            type=PASSWORD,
            label=PASSWORD,
            options=SchemeCredentialQuestion.LINK,
        )
        cls.question_2 = SchemeCredentialQuestionFactory(
            scheme=cls.scheme,
            answer_type=AnswerTypeChoices.TEXT.value,
            manual_question=True,
            label=USER_NAME,
            add_field=True,
        )

        external_id = "test@user.com"
        cls.user = UserFactory(external_id=external_id, client=cls.client_app, email=external_id)

        # Need to add an active association since it was assumed no setting was enabled
        cls.scheme_bundle_association = SchemeBundleAssociationFactory(
            scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        cls.auth_headers = {"HTTP_AUTHORIZATION": "{}".format(cls._get_auth_header(cls.user))}
        cls.version_header = {"HTTP_ACCEPT": "Application/json;v=1.2"}

    @patch("ubiquity.channel_vault._secret_keys", mock_secrets["secret_keys"])
    @patch("ubiquity.channel_vault._bundle_secrets", mock_secrets["bundle_secrets"])
    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    def test_sensitive_field_decryption(self, mock_async_balance, mock_async_link, *_):
        password = "Password1"
        question_answer2 = "some other answer"
        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [
                    {
                        "column": self.question_2.label,
                        "value": question_answer2,
                    }
                ],
                "authorise_fields": [
                    {
                        "column": self.question_1.label,
                        "value": self.rsa.encrypt(password, pub_key=self.pub_key),
                    }
                ],
            },
        }
        resp = self.client.post(
            reverse("membership-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
            **self.version_header,
        )
        self.assertEqual(resp.status_code, 201)

        scheme_account = SchemeAccount.objects.get(pk=resp.data["id"])
        scheme_account_entry = SchemeAccountEntry.objects.get(scheme_account=scheme_account, user=self.user)
        answers = SchemeAccountCredentialAnswer.objects.filter(scheme_account_entry=scheme_account_entry).all()

        self.assertEqual(len(answers), 1)
        self.assertEqual(password, mock_async_link.delay.call_args[0][0][PASSWORD])

        self.assertTrue(mock_async_link.delay.called)
        self.assertFalse(mock_async_balance.delay.called)

    def test_detect_and_handle_escaped_unicode(self):
        passwords = {
            "pa$$w&rd01!@%£Â*🐍": "pa$$w&rd01!@%£Â*🐍",
            "pa\u0024\u0024w\u0026rd01\u0021": "pa$$w&rd01!",
            "pa\\u0024\\u0024w\\u0026rd01\\u0021": "pa$$w&rd01!",
            "pa\\\\u0024\\\\u0024w\\\\u0026rd01\\\\u0021": "pa$$w&rd01!",
            # mixing escaped unicode with non ascii characters is a client error and we wont process it
            "pa\\u0024\\u0024w\\u0026rd01\\u0021ÂÂ££": "pa\\u0024\\u0024w\\u0026rd01\\u0021ÂÂ££",
        }
        test_email = "testunchanged@binkcom"
        for input_password, expected_outcome in passwords.items():
            credential_fields = {"password": input_password, "email": test_email}
            output = detect_and_handle_escaped_unicode(credential_fields)
            self.assertEqual(output["password"], expected_outcome)
            self.assertEqual(output["email"], test_email)

    @patch("ubiquity.channel_vault._secret_keys", mock_secrets["secret_keys"])
    @patch("ubiquity.channel_vault._bundle_secrets", mock_secrets["bundle_secrets"])
    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    def test_double_escaped_sensitive_field_value(self, mock_async_balance, mock_async_link, *_):
        password = "pa\\u0024\\u0024w\\u0026rd01\\u0021"
        expected_password = "pa$$w&rd01!"
        question_answer2 = "some other answer"
        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [
                    {
                        "column": self.question_2.label,
                        "value": question_answer2,
                    }
                ],
                "authorise_fields": [
                    {
                        "column": self.question_1.label,
                        "value": self.rsa.encrypt(password, pub_key=self.pub_key),
                    }
                ],
            },
        }
        resp = self.client.post(
            reverse("membership-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
            **self.version_header,
        )
        self.assertEqual(resp.status_code, 201)

        scheme_account = SchemeAccount.objects.get(pk=resp.data["id"])
        scheme_account_entry = SchemeAccountEntry.objects.get(scheme_account=scheme_account, user=self.user)
        answers = SchemeAccountCredentialAnswer.objects.filter(scheme_account_entry=scheme_account_entry).all()

        self.assertEqual(len(answers), 1)
        self.assertEqual(expected_password, mock_async_link.delay.call_args[0][0][PASSWORD])

        self.assertTrue(mock_async_link.delay.called)
        self.assertFalse(mock_async_balance.delay.called)

    @patch("ubiquity.channel_vault._secret_keys", mock_secrets["secret_keys"])
    @patch("ubiquity.channel_vault._bundle_secrets", mock_secrets["bundle_secrets"])
    @patch("ubiquity.influx_audit.InfluxDBClient")
    @patch("ubiquity.views.async_link", autospec=True)
    @patch("ubiquity.versioning.base.serializers.async_balance", autospec=True)
    @patch.object(MembershipTransactionsMixin, "_get_hades_transactions")
    def test_allow_sensitive_field_not_encrypted(self, *_):
        password = "Password1"
        question_answer2 = "some other answer"
        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [
                    {
                        "column": self.question_2.label,
                        "value": question_answer2,
                    }
                ],
                "authorise_fields": [
                    {
                        "column": self.question_1.label,
                        "value": password,
                    }
                ],
            },
        }
        resp = self.client.post(
            reverse("membership-cards"),
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers,
            **self.version_header,
        )
        self.assertIn(resp.status_code, [200, 201])


class TestLastManStanding(GlobalMockAPITestCase):
    @classmethod
    def _get_auth_header(cls, user):
        token = GenerateJWToken(
            cls.client_app.organisation.name, cls.client_app.secret, cls.bundle.bundle_id, user.external_id
        ).get_token()
        return "Bearer {}".format(token)

    @classmethod
    def setUpTestData(cls) -> None:
        cls.bundle_id = "com.barclays.test"
        organisation = OrganisationFactory(name="test_organisation")
        cls.client_app = ClientApplicationFactory(
            organisation=organisation,
            name="set up client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id=cls.bundle_id, client=cls.client_app)
        cls.scheme = SchemeFactory()

        cls.question_1 = SchemeCredentialQuestionFactory(
            scheme=cls.scheme,
            answer_type=AnswerTypeChoices.SENSITIVE.value,
            auth_field=True,
            type=PASSWORD,
            label=PASSWORD,
            options=SchemeCredentialQuestion.LINK,
        )
        cls.question_2 = SchemeCredentialQuestionFactory(
            scheme=cls.scheme, answer_type=AnswerTypeChoices.TEXT.value, manual_question=True, label=USER_NAME
        )

        external_id_1 = "test_1@user.com"
        external_id_2 = "test_2@user.com"
        cls.user_1 = UserFactory(external_id=external_id_1, client=cls.client_app, email=external_id_1)
        cls.user_2 = UserFactory(external_id=external_id_2, client=cls.client_app, email=external_id_2)

        # Need to add an active association since it was assumed no setting was enabled
        cls.scheme_bundle_association = SchemeBundleAssociationFactory(
            scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        cls.auth_headers_1 = {"HTTP_AUTHORIZATION": "{}".format(cls._get_auth_header(cls.user_1))}
        cls.auth_headers_2 = {"HTTP_AUTHORIZATION": "{}".format(cls._get_auth_header(cls.user_2))}
        cls.version_header = {"HTTP_ACCEPT": "Application/json;v=1.1"}

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("ubiquity.tasks.remove_loyalty_card_event")
    @patch("payment_card.metis.metis_delete_cards_and_activations", autospec=True)
    def test_cards_in_single_property_deletion(self, _, mock_to_warehouse):
        pcard_1 = PaymentCardAccountFactory()
        pcard_2 = PaymentCardAccountFactory()
        mcard = SchemeAccountFactory(scheme=self.scheme)
        PaymentCardAccountEntryFactory(payment_card_account=pcard_1, user=self.user_1)
        PaymentCardAccountEntryFactory(payment_card_account=pcard_2, user=self.user_1)
        SchemeAccountEntryFactory(scheme_account=mcard, user=self.user_1)
        PaymentCardSchemeEntry.objects.create(payment_card_account=pcard_1, scheme_account=mcard)

        self.assertEqual(pcard_1.scheme_account_set.count(), 1)
        self.assertEqual(mcard.payment_card_account_set.count(), 1)

        self.client.delete(reverse("payment-card", args=[pcard_1.id]), **self.auth_headers_1)

        self.assertEqual(mcard.payment_card_account_set.count(), 0)

        PaymentCardSchemeEntry.objects.create(payment_card_account=pcard_2, scheme_account=mcard)
        self.assertEqual(mcard.payment_card_account_set.count(), 1)

        self.client.delete(reverse("membership-card", args=[mcard.id]), **self.auth_headers_1)
        self.assertEqual(pcard_2.scheme_account_set.count(), 0)
        self.assertEqual(mock_to_warehouse.call_count, 1)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("payment_card.metis.metis_delete_cards_and_activations", autospec=True)
    def test_both_cards_in_multiple_property_deletion(self, _):
        pcard = PaymentCardAccountFactory()
        mcard = SchemeAccountFactory(scheme=self.scheme)
        PaymentCardAccountEntryFactory(payment_card_account=pcard, user=self.user_1)
        PaymentCardAccountEntryFactory(payment_card_account=pcard, user=self.user_2)
        SchemeAccountEntryFactory(scheme_account=mcard, user=self.user_1)
        SchemeAccountEntryFactory(scheme_account=mcard, user=self.user_2)
        PaymentCardSchemeEntry.objects.create(payment_card_account=pcard, scheme_account=mcard)

        self.assertEqual(pcard.scheme_account_set.count(), 1)
        self.assertEqual(mcard.payment_card_account_set.count(), 1)

        self.client.delete(reverse("payment-card", args=[pcard.id]), **self.auth_headers_1)
        self.assertEqual(mcard.payment_card_account_set.count(), 1)

        self.client.delete(reverse("membership-card", args=[mcard.id]), **self.auth_headers_1)
        self.assertEqual(pcard.scheme_account_set.count(), 1)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
    @patch("ubiquity.tasks.remove_loyalty_card_event")
    @patch("payment_card.metis.metis_delete_cards_and_activations", autospec=True)
    def test_single_card_in_multiple_property_deletion(self, _, mock_to_warehouse):
        pcard_1 = PaymentCardAccountFactory()
        pcard_2 = PaymentCardAccountFactory()
        mcard = SchemeAccountFactory(scheme=self.scheme)
        PaymentCardAccountEntryFactory(payment_card_account=pcard_1, user=self.user_1)
        PaymentCardAccountEntryFactory(payment_card_account=pcard_1, user=self.user_2)
        SchemeAccountEntryFactory(scheme_account=mcard, user=self.user_1)
        PaymentCardSchemeEntry.objects.create(payment_card_account=pcard_1, scheme_account=mcard)

        self.assertEqual(pcard_1.scheme_account_set.count(), 1)
        self.assertEqual(mcard.payment_card_account_set.count(), 1)

        self.client.delete(reverse("payment-card", args=[pcard_1.id]), **self.auth_headers_1)
        self.assertEqual(mcard.payment_card_account_set.count(), 0)

        PaymentCardAccountEntryFactory(payment_card_account=pcard_2, user=self.user_1)
        SchemeAccountEntryFactory(scheme_account=mcard, user=self.user_2)
        PaymentCardSchemeEntry.objects.create(payment_card_account=pcard_2, scheme_account=mcard)

        self.assertEqual(pcard_2.scheme_account_set.count(), 1)
        self.assertEqual(mcard.payment_card_account_set.count(), 1)

        self.client.delete(reverse("membership-card", args=[mcard.id]), **self.auth_headers_1)
        self.assertEqual(pcard_2.scheme_account_set.count(), 0)

        self.assertEqual(mock_to_warehouse.call_count, 1)

    def test_destroy_link_in_multiple_wallet(self):
        pcard_1 = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(payment_card_account=pcard_1, user=self.user_1)
        PaymentCardAccountEntryFactory(payment_card_account=pcard_1, user=self.user_2)
        mcard = SchemeAccountFactory(scheme=self.scheme)
        SchemeAccountEntryFactory(scheme_account=mcard, user=self.user_1)
        PaymentCardSchemeEntry.objects.create(payment_card_account=pcard_1, scheme_account=mcard)

        response = self.client.delete(reverse("payment-link", args=[mcard.id, pcard_1.id]), **self.auth_headers_1)
        self.assertEqual(response.status_code, 403)

        # Checking membership-link endpoint because it does the same thing as above
        response = self.client.delete(reverse("membership-link", args=[pcard_1.id, mcard.id]), **self.auth_headers_1)
        self.assertEqual(response.status_code, 403)

import json
from unittest.mock import patch

import httpretty
from django.conf import settings
from django.test import override_settings
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from history.models import HistoricalPaymentCardSchemeEntry, HistoricalSchemeAccount, HistoricalVopActivation
from payment_card.tests.factories import PaymentCardFactory, IssuerFactory, PaymentCardAccountFactory
from scheme.credentials import BARCODE, LAST_NAME
from scheme.models import SchemeBundleAssociation, SchemeCredentialQuestion, SchemeAccount
from scheme.tests.factories import (
    SchemeFactory,
    SchemeBundleAssociationFactory,
    SchemeBalanceDetailsFactory,
    SchemeCredentialQuestionFactory,
)
from ubiquity.tests.factories import PaymentCardAccountEntryFactory
from ubiquity.tests.property_token import GenerateJWToken
from user.tests.factories import (
    OrganisationFactory,
    ClientApplicationFactory,
    ClientApplicationBundleFactory,
    UserFactory,
)


def mock_get_cached_balance(self):
    balances = [
        {
            "value": 380,
            "currency": "Points",
            "prefix": "",
            "suffix": "pts",
            "description": "Placeholder Balance Description",
            "updated_at": 1612180595,
            "reward_tier": 1,
        }
    ]
    self.status = 1
    self.balances = balances
    self.save(update_fields=["balances", "status"])
    return balances


@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_TASK_ALWAYS_EAGER=True, BROKER_BACKEND="memory")
class TestTasks(APITestCase):
    @staticmethod
    def _get_auth_header(user, client_app, bundle):
        token = GenerateJWToken(
            client_app.organisation.name, client_app.secret, bundle.bundle_id, user.external_id
        ).get_token()
        return "Bearer {}".format(token)

    @classmethod
    def setUpTestData(cls):
        cls.client_app = ClientApplicationFactory(
            organisation=OrganisationFactory(name="test_organisation"),
            name="set up client application",
            client_id="2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi",
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.auth.fake", client=cls.client_app)
        external_id = "test@user.com"
        cls.user = UserFactory(external_id=external_id, client=cls.client_app, email=external_id)
        cls.scheme = SchemeFactory()
        SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE)
        SchemeBalanceDetailsFactory(scheme_id=cls.scheme)

        SchemeCredentialQuestionFactory(
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

        cls.payment_card_account = PaymentCardAccountFactory(
            issuer=IssuerFactory(name="Barclays"),
            payment_card=PaymentCardFactory(slug="visa", system="visa"),
            hash="5ae741975b4db7bc80072fe8f88f233ef4a67e1e1d7e3bbf68a314dfc6691636",
            status=1,
        )
        cls.payment_card_account_entry = PaymentCardAccountEntryFactory(
            user=cls.user, payment_card_account=cls.payment_card_account
        )

        cls.auth_headers = {"HTTP_AUTHORIZATION": cls._get_auth_header(cls.user, cls.client_app, cls.bundle)}
        cls.version_header = {"HTTP_ACCEPT": "Application/json;v=1.1"}

    @patch("analytics.api")
    @patch.object(SchemeAccount, "get_cached_balance", mock_get_cached_balance)
    @httpretty.activate
    def test_bulk_and_signal_history_resource(self, *_):
        httpretty.register_uri(
            httpretty.POST,
            settings.METIS_URL + "/visa/activate/",
            body=json.dumps({"response_status": 3, "activation_id": "activation id placeholder"}),
            status=201,
        )

        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [{"column": "barcode", "value": "3038401022657083"}],
                "authorise_fields": [{"column": "last_name", "value": "Test"}],
            },
        }

        historical_payment_card_scheme_entry_pre = HistoricalPaymentCardSchemeEntry.objects.count()
        historical_scheme_account_pre = HistoricalSchemeAccount.objects.count()
        historical_vop_activation_pre = HistoricalVopActivation.objects.count()

        resp = self.client.post(
            reverse("membership-cards") + "?autoLink=True",
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers
        )
        self.assertEqual(resp.status_code, 201)

        historical_payment_card_scheme_entry_post = HistoricalPaymentCardSchemeEntry.objects.count()
        historical_scheme_account_post = HistoricalSchemeAccount.objects.count()
        historical_vop_activation_post = HistoricalVopActivation.objects.count()

        self.assertEqual(historical_payment_card_scheme_entry_post, historical_payment_card_scheme_entry_pre + 1)
        self.assertEqual(historical_scheme_account_post, historical_scheme_account_pre + 4)
        self.assertEqual(historical_vop_activation_post, historical_vop_activation_pre + 2)

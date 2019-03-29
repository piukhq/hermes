import datetime
import json
from decimal import Decimal
from unittest.mock import patch

import arrow
import httpretty
from django.conf import settings
from hermes.channels import Permit
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from scheme.models import SchemeBundleAssociation

from payment_card.models import PaymentCardAccount
from payment_card.tests.factories import IssuerFactory, PaymentCardAccountFactory, PaymentCardFactory
from scheme.credentials import (BARCODE, LAST_NAME, PASSWORD)
from scheme.models import SchemeAccount, SchemeCredentialQuestion
from scheme.tests.factories import (SchemeAccountFactory, SchemeBalanceDetailsFactory, SchemeCredentialAnswerFactory,
                                    SchemeCredentialQuestionFactory, SchemeFactory, SchemeBundleAssociationFactory)
from ubiquity.censor_empty_fields import remove_empty
from ubiquity.models import PaymentCardSchemeEntry
from ubiquity.serializers import (MembershipCardSerializer, MembershipPlanSerializer, MembershipTransactionsMixin,
                                  PaymentCardSerializer)
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory, ServiceConsentFactory
from ubiquity.tests.property_token import GenerateJWToken
from ubiquity.views import MembershipTransactionView
from user.tests.factories import (ClientApplicationBundleFactory, ClientApplicationFactory, OrganisationFactory,
                                  UserFactory)


class RequestMock:
        channels_permit = None


class TestResources(APITestCase):

    def setUp(self):
        organisation = OrganisationFactory(name='test_organisation')
        self.client_app = ClientApplicationFactory(organisation=organisation, name='set up client application',
                                                   client_id='2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi')
        self.bundle = ClientApplicationBundleFactory(bundle_id='test.auth.fake', client=self.client_app)
        external_id = 'test@user.com'
        self.user = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        self.scheme = SchemeFactory()
        SchemeBalanceDetailsFactory(scheme_id=self.scheme)

        SchemeCredentialQuestionFactory(scheme=self.scheme, type=BARCODE, label=BARCODE, manual_question=True)
        self.secondary_question = SchemeCredentialQuestionFactory(scheme=self.scheme,
                                                                  type=LAST_NAME,
                                                                  label=LAST_NAME,
                                                                  third_party_identifier=True,
                                                                  options=SchemeCredentialQuestion.LINK,
                                                                  auth_field=True)
        self.scheme_account = SchemeAccountFactory(scheme=self.scheme)
        self.scheme_account_answer = SchemeCredentialAnswerFactory(question=self.scheme.manual_question,
                                                                   scheme_account=self.scheme_account)
        self.second_scheme_account_answer = SchemeCredentialAnswerFactory(question=self.secondary_question,
                                                                          scheme_account=self.scheme_account)
        self.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=self.scheme_account, user=self.user)

        # Need to add an active association since it was assumed no setting was enabled
        self.scheme_bundle_association = SchemeBundleAssociationFactory(scheme=self.scheme, bundle=self.bundle,
                                                                        status=SchemeBundleAssociation.ACTIVE)

        self.issuer = IssuerFactory(name='Barclays')
        self.payment_card = PaymentCardFactory(slug='visa', system='visa')
        self.payment_card_account = PaymentCardAccountFactory(issuer=self.issuer, payment_card=self.payment_card)
        self.payment_card_account_entry = PaymentCardAccountEntryFactory(user=self.user,
                                                                         payment_card_account=self.payment_card_account)
        token = GenerateJWToken(self.client_app.organisation.name, self.client_app.secret, self.bundle.bundle_id,
                                external_id).get_token()
        self.auth_headers = {'HTTP_AUTHORIZATION': 'Bearer {}'.format(token)}

    def test_get_single_payment_card(self):
        payment_card_account = self.payment_card_account_entry.payment_card_account
        expected_result = remove_empty(PaymentCardSerializer(payment_card_account).data)
        resp = self.client.get(reverse('payment-card', args=[payment_card_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    def test_update_payment_card(self):
        payment_card_account = self.payment_card_account_entry.payment_card_account
        new_data = {
            "card": {
                "name_on_card": "new name on card"
            }
        }
        resp = self.client.patch(reverse('payment-card', args=[payment_card_account.id]), data=json.dumps(new_data),
                                 content_type='application/json', **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['card']['name_on_card'], new_data['card']['name_on_card'])

        new_consent = {
            "account": {
                "consents": [
                    {
                        "timestamp": 23947329497,
                        "type": 0
                    }
                ]
            }
        }
        resp = self.client.patch(reverse('payment-card', args=[payment_card_account.id]), data=json.dumps(new_consent),
                                 content_type='application/json', **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['account']['consents'], new_consent['account']['consents'])

    def test_get_all_payment_cards(self):
        PaymentCardAccountEntryFactory(user=self.user)
        payment_card_accounts = PaymentCardAccount.objects.filter(user_set__id=self.user.id).all()
        expected_result = remove_empty(PaymentCardSerializer(payment_card_accounts, many=True).data)
        resp = self.client.get(reverse('payment-cards'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_get_single_membership_card(self, mock_get_midas_balance, *_):
        mock_get_midas_balance.return_value = self.scheme_account.balances
        resp = self.client.get(reverse('membership-card', args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_get_all_membership_cards(self, *_):
        scheme_account_2 = SchemeAccountFactory(balances=self.scheme_account.balances)
        SchemeAccountEntryFactory(scheme_account=scheme_account_2, user=self.user)
        scheme_accounts = SchemeAccount.objects.filter(user_set__id=self.user.id).all()
        expected_result = remove_empty(MembershipCardSerializer(scheme_accounts, many=True).data)
        resp = self.client.get(reverse('membership-cards'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result[0]['account'], resp.json()[0]['account'])

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_creation(self, *_):
        payload = {
            "card": {
                "last_four_digits": 5234,
                "currency_code": "GBP",
                "first_six_digits": 523456,
                "name_on_card": "test user 2",
                "token": "H7FdKWKPOPhepzxS4MfUuvTDHxr",
                "fingerprint": "b5fe350d5135ab64a8f3c1097fadefd9effb",
                "year": 22,
                "month": 3,
                "order": 1
            },
            "account": {
                "consents": [
                    {
                        "timestamp": 1517549941,
                        "type": 0
                    }
                ]
            }
        }
        resp = self.client.post(reverse('payment-cards'), data=json.dumps(payload),
                                content_type='application/json', **self.auth_headers)
        self.assertEqual(resp.status_code, 201)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_replace(self, *_):
        pca = PaymentCardAccountFactory(token='original-token')
        PaymentCardAccountEntryFactory(user=self.user, payment_card_account=pca)
        correct_payload = {
            "card": {
                "last_four_digits": "5234",
                "currency_code": "GBP",
                "first_six_digits": "523456",
                "name_on_card": "test user 2",
                "token": "token-to-ignore",
                "fingerprint": str(pca.fingerprint),
                "year": 22,
                "month": 3,
                "order": 1
            },
            "account": {
                "consents": [
                    {
                        "timestamp": 1517549941,
                        "type": 0
                    }
                ]
            }
        }
        resp = self.client.put(reverse('payment-card', args=[pca.id]), data=json.dumps(correct_payload),
                               content_type='application/json', **self.auth_headers)
        pca.refresh_from_db()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(pca.token, 'original-token')
        self.assertEqual(pca.pan_end, correct_payload['card']['last_four_digits'])

        wrong_payload = {
            "card": {
                "last_four_digits": "5234",
                "currency_code": "GBP",
                "first_six_digits": "523456",
                "name_on_card": "test user 2",
                "token": "token-to-ignore",
                "fingerprint": "this-is-not-{}".format(pca.fingerprint),
                "year": 22,
                "month": 3,
                "order": 1
            },
            "account": {
                "consents": [
                    {
                        "timestamp": 1517549941,
                        "type": 0
                    }
                ]
            }
        }
        resp = self.client.put(reverse('payment-card', args=[pca.id]), data=json.dumps(wrong_payload),
                               content_type='application/json', **self.auth_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['detail'], 'cannot override fingerprint.')

    @patch('analytics.api.update_scheme_account_attribute')
    @patch('ubiquity.influx_audit.InfluxDBClient')
    @patch('analytics.api.post_event')
    @patch('analytics.api.update_scheme_account_attribute')
    @patch('analytics.api._send_to_mnemosyne')
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch('analytics.api._get_today_datetime')
    def test_membership_card_creation(self, mock_date, mock_hades, mock_async_balance, mock_async_link, *_):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": "3038401022657083"
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": "last_name",
                            "value": "Test"
                        }
                    ]
                }
        }
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                **self.auth_headers)
        self.assertEqual(resp.status_code, 201)
        create_data = resp.data
        # replay and check same data with 200 response
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertDictEqual(resp.data, create_data)
        self.assertTrue(mock_hades.called)
        self.assertTrue(mock_async_link.delay.called)
        self.assertFalse(mock_async_balance.delay.called)

    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_membership_card_update(self, *_):
        payload = json.dumps({
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": "3038401022657083"
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": "last_name",
                            "value": "Test"
                        }
                    ]
                }
        })
        response = self.client.patch(reverse('membership-card', args=[self.scheme_account.id]),
                                     content_type='application/json', data=payload, **self.auth_headers)
        self.assertEqual(response.status_code, 200)

    @patch('analytics.api.update_scheme_account_attribute')
    @patch('ubiquity.influx_audit.InfluxDBClient')
    @patch('analytics.api.post_event')
    @patch('analytics.api.update_scheme_account_attribute')
    @patch('analytics.api._send_to_mnemosyne')
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch('analytics.api._get_today_datetime')
    def test_membership_card_delete(self, mock_date, *_):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": "3038401022657083"
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": "last_name",
                            "value": "Test"
                        }
                    ]
                }
        }
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                **self.auth_headers)
        self.assertEqual(resp.status_code, 201)
        create_data = resp.data
        # replay and check same data with 200 response
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertDictEqual(resp.data, create_data)
        account_id = resp.data['id']

        resp_del = self.client.delete(reverse('membership-card', args=[account_id]), data="{}",
                                      content_type='application/json', **self.auth_headers)
        self.assertEqual(resp_del.status_code, 200)
        resp2 = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                 **self.auth_headers)
        self.assertEqual(resp2.status_code, 201)

    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_cards_linking(self, *_):
        payment_card_account = self.payment_card_account_entry.payment_card_account
        scheme_account_2 = SchemeAccountFactory(scheme=self.scheme)
        SchemeAccountEntryFactory(user=self.user, scheme_account=scheme_account_2)
        PaymentCardSchemeEntry.objects.create(payment_card_account=payment_card_account,
                                              scheme_account=self.scheme_account)
        params = [
            payment_card_account.id,
            scheme_account_2.id
        ]
        resp = self.client.patch(reverse('membership-link', args=params), **self.auth_headers)
        self.assertEqual(resp.status_code, 201)

        links_data = PaymentCardSerializer(payment_card_account).data['membership_cards']
        for link in links_data:
            if link['id'] == self.scheme_account.id:
                self.assertEqual(link['active_link'], False)
            elif link['id'] == scheme_account_2.id:
                self.assertEqual(link['active_link'], True)

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

    def test_membership_card_delete_removes_link_for_cards_not_shared_between_users(self):

        entry = PaymentCardSchemeEntry.objects.create(payment_card_account=self.payment_card_account,
                                                      scheme_account=self.scheme_account)

        resp = self.client.delete(reverse('membership-card', args=[self.scheme_account.id]),
                                  data="{}",
                                  content_type='application/json', **self.auth_headers)

        self.assertEqual(resp.status_code, 200)

        link = PaymentCardSchemeEntry.objects.filter(pk=entry.pk)
        self.assertEqual(len(link), 0)

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

    @patch('requests.delete')
    def test_payment_card_delete_removes_link_for_cards_not_shared_between_users(self, mock_request_delete):
        entry = PaymentCardSchemeEntry.objects.create(payment_card_account=self.payment_card_account,
                                                      scheme_account=self.scheme_account)

        resp = self.client.delete(reverse('payment-card', args=[self.payment_card_account.id]),
                                  data="{}",
                                  content_type='application/json', **self.auth_headers)

        self.assertTrue(mock_request_delete.called)
        self.assertEqual(resp.status_code, 200)

        link = PaymentCardSchemeEntry.objects.filter(pk=entry.pk)
        self.assertEqual(len(link), 0)

    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_card_rule_filtering(self, *_):
        resp_payment = self.client.get(reverse('payment-card', args=[self.payment_card_account.id]),
                                       **self.auth_headers)
        resp_membership = self.client.get(reverse('membership-card', args=[self.scheme_account.id]),
                                          **self.auth_headers)
        self.assertEqual(resp_payment.status_code, 200)
        self.assertEqual(resp_membership.status_code, 200)

        self.bundle.issuer.add(IssuerFactory())
        self.scheme_bundle_association = SchemeBundleAssociationFactory(scheme=SchemeFactory(), bundle=self.bundle,
                                                                        status=SchemeBundleAssociation.ACTIVE)

        resp_payment = self.client.get(reverse('payment-card', args=[self.payment_card_account.id]),
                                       **self.auth_headers)
        resp_membership = self.client.get(reverse('membership-card', args=[self.scheme_account.id]),
                                          **self.auth_headers)
        self.assertEqual(resp_payment.status_code, 404)
        self.assertEqual(resp_membership.status_code, 404)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.serializers.async_balance', autospec=True)
    def test_card_creation_filter(self, *_):
        self.bundle.issuer.add(IssuerFactory())

        payload = {
            "card": {
                "last_four_digits": 5234,
                "currency_code": "GBP",
                "first_six_digits": 523456,
                "name_on_card": "test user 2",
                "token": "H7FdKWKPOPhepzxS4MfUuvTDHxr",
                "fingerprint": "b5fe350d5135ab64a8f3c1097fadefd9effb",
                "year": 22,
                "month": 3,
                "order": 1
            },
            "account": {
                "consents": [
                    {
                        "timestamp": 1517549941,
                        "type": 0
                    }
                ]
            }
        }
        resp = self.client.post(reverse('payment-cards'), data=json.dumps(payload),
                                content_type='application/json', **self.auth_headers)
        self.assertIn('issuer not allowed', resp.json()['detail'])

        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [
                    {
                        "column": "barcode",
                        "value": "3038401022657083"
                    }
                ]
            }
        }
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                **self.auth_headers)
        self.assertIn('membership plan not allowed', resp.json()['detail'])

    @httpretty.activate
    def test_membership_transactions(self):
        uri = '{}/transactions/scheme_account/{}'.format(settings.HADES_URL, self.scheme_account.id)
        transactions = json.dumps([
            {
                'id': 1,
                'scheme_account_id': self.scheme_account.id,
                'created': arrow.utcnow().format(),
                'date': arrow.utcnow().format(),
                'description': 'Test Transaction',
                'location': 'Bink',
                'points': 200,
                'value': 'A lot',
                'hash': 'ewfnwoenfwen'
            }
        ])
        httpretty.register_uri(httpretty.GET, uri, transactions)
        resp = self.client.get(reverse('membership-card-transactions', args=[self.scheme_account.id]),
                               **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(httpretty.has_request())

        uri = '{}/transactions/user/{}'.format(settings.HADES_URL, self.user.id)
        httpretty.register_uri(httpretty.GET, uri, transactions)
        resp = self.client.get(reverse('membership-card-transactions', args=[self.scheme_account.id]),
                               **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]['amounts'][0]['value'], 200)
        self.assertTrue(httpretty.has_request())

        uri = '{}/transactions/1'.format(settings.HADES_URL)
        transaction = json.dumps({
            'id': 1,
            'scheme_account_id': self.scheme_account.id,
            'created': arrow.utcnow().format(),
            'date': arrow.utcnow().format(),
            'description': 'Test Transaction',
            'location': 'Bink',
            'points': 200,
            'value': 'A lot',
            'hash': 'ewfnwoenfwen'
        })
        httpretty.register_uri(httpretty.GET, uri, transaction)
        resp = self.client.get(reverse('membership-card-transactions', args=[self.scheme_account.id]),
                               **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(httpretty.has_request())

    def test_composite_payment_card_get(self):
        resp = self.client.get(reverse('composite-payment-cards', args=[self.scheme_account.id]),
                               **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_composite_payment_card_post(self, *_):
        new_sa = SchemeAccountEntryFactory(user=self.user).scheme_account
        payload = {
            "card": {
                "last_four_digits": 5234,
                "currency_code": "GBP",
                "first_six_digits": 523456,
                "name_on_card": "test user 2",
                "token": "H7FdKWKPOPhepzxS4MfUuvTDHxr",
                "fingerprint": "b5fe350d5135ab64a8f3c1097fadefd9effb",
                "year": 22,
                "month": 3,
                "order": 1
            },
            "account": {
                "consents": [
                    {
                        "timestamp": 1517549941,
                        "type": 0
                    }
                ]
            }
        }
        expected_links = [
            {
                'id': new_sa.id,
                'active_link': True
            }
        ]

        resp = self.client.post(reverse('composite-payment-cards', args=[new_sa.id]), data=json.dumps(payload),
                                content_type='application/json', **self.auth_headers)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(expected_links, resp.json()['membership_cards'])

    @patch('ubiquity.serializers.async_balance', autospec=True)
    def test_composite_membership_card_get(self, _):
        resp = self.client.get(reverse('composite-membership-cards', args=[self.payment_card_account.id]),
                               **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

    @patch('analytics.api.post_event')
    @patch('analytics.api.update_scheme_account_attribute')
    @patch('analytics.api._send_to_mnemosyne')
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch('analytics.api._get_today_datetime')
    def test_composite_membership_card_post(self, mock_date, *_):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        new_pca = PaymentCardAccountEntryFactory(user=self.user).payment_card_account

        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [
                    {
                        "column": "barcode",
                        "value": "1234401022657083"
                    }
                ],
                "authorise_fields": [
                    {
                        "column": "last_name",
                        "value": "Test Composite"
                    }
                ]
            }
        }
        expected_links = {
            'id': new_pca.id,
            'active_link': True
        }

        resp = self.client.post(reverse('composite-membership-cards', args=[new_pca.id]), data=json.dumps(payload),
                                content_type='application/json', **self.auth_headers)
        self.assertEqual(resp.status_code, 201)
        self.assertIn(expected_links, resp.json()['payment_cards'])

    @patch('scheme.mixins.analytics', autospec=True)
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_membership_card_put_and_composite_post(self, *_):
        new_pca = PaymentCardAccountEntryFactory(user=self.user).payment_card_account
        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [
                    {
                        "column": "barcode",
                        "value": "1234401022657083"
                    }
                ],
                "authorise_fields": [
                    {
                        "column": "last_name",
                        "value": "Test Composite"
                    }
                ]
            }
        }
        expected_links = {
            'id': new_pca.id,
            'active_link': True
        }

        resp = self.client.post(reverse('composite-membership-cards', args=[new_pca.id]), data=json.dumps(payload),
                                content_type='application/json', **self.auth_headers)
        account_id = resp.data['id']
        self.assertEqual(resp.status_code, 201)
        self.assertIn(expected_links, resp.json()['payment_cards'])

        payment_link = PaymentCardSchemeEntry.objects.filter(scheme_account=account_id, payment_card_account=new_pca.id)
        self.assertEqual(1, payment_link.count())

        payload_put = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [
                    {
                        "column": "barcode",
                        "value": "1234401022699099"
                    }
                ],
                "authorise_fields": [
                    {
                        "column": "last_name",
                        "value": "Test Composite"
                    }
                ]
            }
        }
        resp_put = self.client.put(reverse('membership-card', args=[account_id]), data=json.dumps(payload_put),
                                   content_type='application/json', **self.auth_headers)
        self.assertEqual(resp_put.status_code, 200)
        self.assertEqual(account_id, resp_put.data['id'])
        scheme_account = SchemeAccount.objects.get(id=account_id)
        self.assertEqual(account_id, scheme_account.id)
        self.assertEqual(resp_put.json()['card']['barcode'], "1234401022699099")
        self.assertTrue(payment_link.exists())

    @patch('scheme.mixins.analytics', autospec=True)
    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch('ubiquity.views.async_registration', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_membership_card_patch(self, *_):
        sa = SchemeAccountFactory(scheme=self.scheme)
        SchemeAccountEntryFactory(user=self.user, scheme_account=sa)
        SchemeCredentialAnswerFactory(question=self.secondary_question, scheme_account=sa, answer='name')
        expected_value = {'last_name': 'changed name'}
        payload_update = {
            "account": {
                "authorise_fields": [
                    {
                        "column": "last_name",
                        "value": "changed name"
                    }
                ]
            }
        }
        resp_update = self.client.patch(reverse('membership-card', args=[sa.id]), data=json.dumps(payload_update),
                                        content_type='application/json', **self.auth_headers)
        self.assertEqual(resp_update.status_code, 200)
        sa.refresh_from_db()
        self.assertEqual(sa._collect_credentials()['last_name'], expected_value['last_name'])

        payload_register = {
            "account": {
                "registration_fields": [
                    {
                        "column": "last_name",
                        "value": "changed name"
                    }
                ]
            }
        }
        resp_register = self.client.patch(reverse('membership-card', args=[sa.id]), data=json.dumps(payload_register),
                                          content_type='application/json', **self.auth_headers)
        self.assertEqual(resp_register.status_code, 200)

    def test_membership_plans(self):
        resp = self.client.get(reverse('membership-plans'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(isinstance(resp.json(), list))

    def test_membership_plan(self):
        resp = self.client.get(reverse('membership-plan', args=[self.scheme.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

        RequestMock.channels_permit = Permit(self.bundle.bundle_id, client=self.client)
        context = {'request': RequestMock}
        self.assertEqual(remove_empty(MembershipPlanSerializer(self.scheme, context=context).data), resp.json())

    def test_composite_membership_plan(self):
        RequestMock.channels_permit = Permit(self.bundle.bundle_id, client=self.client)
        context = {'request': RequestMock}
        expected_result = remove_empty(MembershipPlanSerializer(self.scheme_account.scheme, context=context).data)

        resp = self.client.get(reverse('membership-card-plan', args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_membership_card_balance(self, mock_get_midas_balance, *_):
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'reward_tier': 0,
            'balance': Decimal('20'),
            'is_stale': False
        }
        expected_keys = {'value', 'currency', 'updated_at'}
        self.scheme_account.get_cached_balance()
        resp = self.client.get(reverse('membership-card', args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['balances'][0]['value'], 100)
        self.assertTrue(expected_keys.issubset(set(resp.json()['balances'][0].keys())))

    @patch('analytics.api.update_scheme_account_attribute')
    @patch('ubiquity.influx_audit.InfluxDBClient')
    @patch('analytics.api.post_event')
    @patch('analytics.api._send_to_mnemosyne')
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch('analytics.api._get_today_datetime')
    def test_existing_membership_card_creation_fail(self, mock_date, *_):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": self.scheme_account.barcode
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": "last_name",
                            "value": "Test Fail"
                        }
                    ]
                }
        }
        new_external_id = 'Test User 2'
        new_user = UserFactory(external_id=new_external_id, client=self.client_app, email=new_external_id)
        PaymentCardAccountEntryFactory(user=new_user, payment_card_account=self.payment_card_account)
        new_token = GenerateJWToken(self.client_app.organisation.name, self.client_app.secret, self.bundle.bundle_id,
                                    new_external_id).get_token()

        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                HTTP_AUTHORIZATION='Bearer {}'.format(new_token))
        self.assertEqual(resp.status_code, 400)
        self.assertIn(
            'This card already exists, but the provided credentials do not match.',
            resp.json().get('detail')
        )

    def test_membership_plan_serializer_method(self):
        serializer = MembershipPlanSerializer()
        test_dict = [
            {'column': 1},
            {'column': 2},
            {'column': 3}
        ]
        expected = [
            {'column': 1, 'alternatives': [2, 3]},
            {'column': 2, 'alternatives': [1, 3]},
            {'column': 3, 'alternatives': [1, 2]}
        ]
        serializer._add_alternatives_key(test_dict)
        self.assertEqual(expected, test_dict)

    @patch('ubiquity.views.async_all_balance.delay')
    def test_get_service(self, mock_async_all_balance):
        ServiceConsentFactory(user=self.user)
        resp = self.client.get(reverse('service'), **self.auth_headers)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_async_all_balance.called)
        self.assertEqual(mock_async_all_balance.call_args[0][0], self.user.id)

    @patch('scheme.mixins.analytics', autospec=True)
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_auto_link(self, *_):
        external_id = 'test auto link'
        user = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        token = GenerateJWToken(self.client_app.organisation.name, self.client_app.secret, self.bundle.bundle_id,
                                external_id).get_token()
        auth_headers = {'HTTP_AUTHORIZATION': 'Bearer {}'.format(token)}
        payment_card_account = PaymentCardAccountFactory(issuer=self.issuer, payment_card=self.payment_card)
        PaymentCardAccountEntryFactory(user=user, payment_card_account=payment_card_account)
        query = {'payment_card_account_id': payment_card_account.id}

        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": "123456789"
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": "last_name",
                            "value": "Test Successful Link"
                        }
                    ]
                }
        }
        success_resp = self.client.post(f'{reverse("membership-cards")}?autoLink=True', data=json.dumps(payload),
                                        content_type='application/json', **auth_headers)

        self.assertEqual(success_resp.status_code, 201)
        query['scheme_account_id'] = success_resp.json()['id']
        self.assertTrue(PaymentCardSchemeEntry.objects.filter(**query).exists())

        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": "987654321"
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": "last_name",
                            "value": "Test Excluded Link"
                        }
                    ]
                }
        }
        fail_resp = self.client.post(f'{reverse("membership-cards")}?autoLink=True', data=json.dumps(payload),
                                     content_type='application/json', **auth_headers)

        self.assertEqual(fail_resp.status_code, 201)
        query['scheme_account_id'] = fail_resp.json()['id']
        self.assertFalse(PaymentCardSchemeEntry.objects.filter(**query).exists())

    def test_membership_card_transactions_user_filters(self):
        sae_correct = SchemeAccountEntryFactory(user=self.user)
        sae_wrong = SchemeAccountEntryFactory()
        data = [
            {'scheme_account_id': sae_correct.scheme_account_id},
            {'scheme_account_id': sae_wrong.scheme_account_id},
            {'scheme_account_id': sae_wrong.scheme_account_id},
            {'scheme_account_id': sae_wrong.scheme_account_id},
            {'scheme_account_id': sae_correct.scheme_account_id},
            {'scheme_account_id': sae_wrong.scheme_account_id}
        ]
        filtered_data = MembershipTransactionView._filter_transactions_for_current_user(self.user.id, data)
        self.assertEqual(len(filtered_data), 2)
        self.assertTrue(MembershipTransactionView._account_belongs_to_user(self.user.id, sae_correct.scheme_account_id))
        self.assertFalse(MembershipTransactionView._account_belongs_to_user(self.user.id, sae_wrong.scheme_account_id))


class TestMembershipCardCredentials(APITestCase):
    def setUp(self):
        organisation = OrganisationFactory(name='set up authentication for credentials')
        client = ClientApplicationFactory(organisation=organisation, name='set up credentials application')
        bundle = ClientApplicationBundleFactory(bundle_id='test.credentials.fake', client=client)
        external_id = 'credentials@user.com'
        self.user = UserFactory(external_id=external_id, client=client, email=external_id)
        self.scheme = SchemeFactory()
        SchemeBalanceDetailsFactory(scheme_id=self.scheme)
        SchemeCredentialQuestionFactory(scheme=self.scheme, type=BARCODE, label=BARCODE, manual_question=True,
                                        add_field=True)
        SchemeCredentialQuestionFactory(scheme=self.scheme, type=PASSWORD, label=PASSWORD, auth_field=True)
        secondary_question = SchemeCredentialQuestionFactory(scheme=self.scheme,
                                                             type=LAST_NAME,
                                                             label=LAST_NAME,
                                                             third_party_identifier=True,
                                                             options=SchemeCredentialQuestion.LINK,
                                                             auth_field=True)
        self.scheme_account = SchemeAccountFactory(scheme=self.scheme)
        self.scheme_account_answer = SchemeCredentialAnswerFactory(question=self.scheme.manual_question,
                                                                   scheme_account=self.scheme_account)
        self.second_scheme_account_answer = SchemeCredentialAnswerFactory(question=secondary_question,
                                                                          scheme_account=self.scheme_account)
        self.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=self.scheme_account, user=self.user)
        token = GenerateJWToken(client.organisation.name, client.secret, bundle.bundle_id, external_id).get_token()
        self.auth_headers = {'HTTP_AUTHORIZATION': 'Bearer {}'.format(token)}

    @patch('ubiquity.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_update_new_and_existing_credentials(self, *_):
        payload = {
            'account': {
                'authorise_fields': [
                    {
                        'column': 'last_name',
                        'value': 'New Last Name'
                    },
                    {
                        'column': 'password',
                        'value': 'newpassword'
                    }
                ]
            }
        }
        resp = self.client.patch(reverse('membership-card', args=[self.scheme_account.id]), data=json.dumps(payload),
                                 content_type='application/json', **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

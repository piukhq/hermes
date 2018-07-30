import json
from decimal import Decimal
from unittest.mock import patch

import arrow
import httpretty
from django.conf import settings
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from payment_card.models import PaymentCardAccount
from payment_card.tests.factories import IssuerFactory
from scheme.credentials import BARCODE, LAST_NAME
from scheme.models import SchemeAccount, SchemeCredentialQuestion
from scheme.tests.factories import (SchemeAccountFactory, SchemeCredentialAnswerFactory,
                                    SchemeCredentialQuestionFactory, SchemeFactory)
from ubiquity.models import PaymentCardSchemeEntry
from ubiquity.serializers import ListMembershipCardSerializer, MembershipCardSerializer, PaymentCardSerializer
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory
from ubiquity.tests.property_token import GenerateJWToken
from user.models import CustomUser
from user.tests.factories import ClientApplicationBundleFactory, UserFactory


class TestRegistration(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = ClientApplicationBundleFactory()
        cls.token_generator = GenerateJWToken
        super().setUpClass()

    def test_service_registration(self):
        data = {
            'client_id': self.bundle.client.client_id,
            'secret': self.bundle.client.secret,
            'bundle_id': self.bundle.bundle_id
        }
        token = self.token_generator(**data).get_token()
        auth_headers = {'HTTP_AUTHORIZATION': 'bearer {}'.format(token)}
        consent = json.dumps({
            'consent': {
                'timestamp': arrow.utcnow().timestamp
            }
        })

        resp = self.client.post('/ubiquity/service', data=consent, content_type='application/json', **auth_headers)
        self.assertEqual(resp.status_code, 200)

    def test_service_registration_wrong_data(self):
        data = {
            'client_id': self.bundle.client.client_id,
            'secret': self.bundle.client.secret,
            'bundle_id': self.bundle.bundle_id,
            'email': 'wrongconsent@bink.test'
        }
        token = self.token_generator(**data).get_token()
        auth_headers = {'HTTP_AUTHORIZATION': 'token {}'.format(token)}
        consent = {
            'latitude': 12.234,
            'longitude': 56.856,
            'timestamp': 'not a timestamp'
        }

        wrong_consent_resp = self.client.post('/ubiquity/service', data=consent, **auth_headers)
        self.assertEqual(wrong_consent_resp.status_code, 400)
        self.assertIn('timestamp', wrong_consent_resp.json())

        with self.assertRaises(CustomUser.DoesNotExist):
            CustomUser.objects.get(email='{}__{}'.format(data['bundle_id'], data['email']))

    def test_service_registration_wrong_header(self):
        data = {
            'client_id': self.bundle.client.client_id,
            'secret': self.bundle.client.secret,
            'bundle_id': 'wrong bundle id'
        }
        token = self.token_generator(**data).get_token()
        auth_headers = {'HTTP_AUTHORIZATION': 'token {}'.format(token)}
        consent = {
            'latitude': 12.234,
            'longitude': 56.856,
            'timestamp': arrow.utcnow().timestamp
        }

        wrong_header_resp = self.client.post('/ubiquity/service', data=consent, **auth_headers)
        self.assertEqual(wrong_header_resp.status_code, 403)
        self.assertIn('Invalid token', wrong_header_resp.json()['detail'])


class TestResources(APITestCase):

    def setUp(self):
        bundle = ClientApplicationBundleFactory()
        client = bundle.client
        email = 'test@user.com'
        self.user = UserFactory(email='{}__{}'.format(bundle.bundle_id, email))
        self.scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=self.scheme, type=BARCODE, manual_question=True)
        secondary_question = SchemeCredentialQuestionFactory(scheme=self.scheme,
                                                             type=LAST_NAME,
                                                             third_party_identifier=True,
                                                             options=SchemeCredentialQuestion.LINK)
        self.scheme_account = SchemeAccountFactory(scheme=self.scheme)
        self.scheme_account_answer = SchemeCredentialAnswerFactory(question=self.scheme.manual_question,
                                                                   scheme_account=self.scheme_account)
        self.second_scheme_account_answer = SchemeCredentialAnswerFactory(question=secondary_question,
                                                                          scheme_account=self.scheme_account)
        self.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=self.scheme_account, user=self.user)

        self.payment_card_account_entry = PaymentCardAccountEntryFactory(user=self.user)
        self.payment_card_account = self.payment_card_account_entry.payment_card_account
        self.payment_card = self.payment_card_account.payment_card

        token = GenerateJWToken(client.client_id, client.secret, bundle.bundle_id, email).get_token()
        self.auth_headers = {'HTTP_AUTHORIZATION': 'Bearer {}'.format(token)}

    def test_get_single_payment_card(self):
        payment_card_account = self.payment_card_account_entry.payment_card_account
        expected_result = PaymentCardSerializer(payment_card_account).data
        resp = self.client.get(reverse('payment-card', args=[payment_card_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    def test_get_all_payment_cards(self):
        PaymentCardAccountEntryFactory(user=self.user)
        payment_card_accounts = PaymentCardAccount.objects.filter(user_set__id=self.user.id).all()
        expected_result = PaymentCardSerializer(payment_card_accounts, many=True).data
        resp = self.client.get(reverse('payment-cards'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_get_single_membership_card(self, mock_get_midas_balance):
        mock_get_midas_balance.return_value = self.scheme_account.balance
        expected_result = MembershipCardSerializer(self.scheme_account).data

        resp = self.client.get(reverse('membership-card', args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_get_all_membership_cards(self, mock_get_midas_balance):
        mock_get_midas_balance.return_value = self.scheme_account.balance
        scheme_account_2 = SchemeAccountFactory(balance=self.scheme_account.balance)
        SchemeAccountEntryFactory(scheme_account=scheme_account_2, user=self.user)
        scheme_accounts = SchemeAccount.objects.filter(user_set__id=self.user.id).all()
        expected_result = ListMembershipCardSerializer(scheme_accounts, many=True).data

        resp = self.client.get(reverse('membership-cards'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    @patch('intercom.intercom_api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_creation(self, *_):
        payload = {
            "card": {
                "last_four_digits": 5234,
                "currency_code": "GBP",
                "first_six_digits": 523456,
                "provider": self.payment_card_account_entry.payment_card_account.issuer.id,
                "payment_card": self.payment_card_account_entry.payment_card_account.payment_card.id,
                "name_on_card": "test user 2",
                "token": "H7FdKWKPOPhepzxS4MfUuvTDHxr",
                "fingerprint": "b5fe350d5135ab64a8f3c1097fadefd9effb",
                "year": 22,
                "month": 3,
                "country": "UK",
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

    @patch('intercom.intercom_api')
    @patch('ubiquity.influx_audit.InfluxDBClient')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_create_membership_card_creation(self, mock_get_midas_balance, *_):
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'reward_tier': 0,
            'balance': Decimal('20'),
            'is_stale': False
        }
        payload = {
            "order": 1,
            "membership_plan": self.scheme.id,
            "barcode": "3038401022657083",
            "last_name": "Test"
        }
        resp = self.client.post(reverse('membership-cards'), data=payload, **self.auth_headers)
        self.assertEqual(resp.status_code, 201)

    def test_cards_linking(self):
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

    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_card_rule_filtering(self, mock_get_midas_balance):
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'reward_tier': 0,
            'balance': Decimal('20'),
            'is_stale': False
        }

        resp_payment = self.client.get(reverse('payment-card', args=[self.payment_card_account.id]),
                                       **self.auth_headers)
        resp_membership = self.client.get(reverse('membership-card', args=[self.scheme_account.id]),
                                          **self.auth_headers)
        self.assertEqual(resp_payment.status_code, 200)
        self.assertEqual(resp_membership.status_code, 200)

        self.user.client.organisation.issuers.add(IssuerFactory())
        self.user.client.organisation.schemes.add(SchemeFactory())

        resp_payment = self.client.get(reverse('payment-card', args=[self.payment_card_account.id]),
                                       **self.auth_headers)
        resp_membership = self.client.get(reverse('membership-card', args=[self.scheme_account.id]),
                                          **self.auth_headers)
        self.assertEqual(resp_payment.status_code, 404)
        self.assertEqual(resp_membership.status_code, 404)

    @patch('intercom.intercom_api')
    @patch('payment_card.metis.enrol_new_payment_card')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_card_creation_filter(self, mock_get_midas_balance, *_):
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'reward_tier': 0,
            'balance': Decimal('20'),
            'is_stale': False
        }
        self.user.client.organisation.issuers.add(IssuerFactory())
        self.user.client.organisation.schemes.add(SchemeFactory())

        payload = {
            "card": {
                "pan_end": 5234,
                "currency_code": "GBP",
                "pan_start": 523456,
                "issuer": self.payment_card_account_entry.payment_card_account.issuer.id,
                "payment_card": self.payment_card_account_entry.payment_card_account.payment_card.id,
                "name_on_card": "test user 2",
                "token": "abc2",
                "fingerprint": "weqrewqewr32423q",
                "expiry_year": 22,
                "expiry_month": 3,
                "country": "UK",
                "order": 1
            },
            "account": {
                "consent": {
                    "latitude": 51.405372,
                    "longitude": -0.678357,
                    "timestamp": 1517549941
                }
            }
        }
        resp = self.client.post(reverse('payment-cards'), data=json.dumps(payload),
                                content_type='application/json', **self.auth_headers)
        self.assertIn('issuer not allowed', resp.json()['detail'])

        payload = {
            "order": 1,
            "membership_plan": self.scheme.id,
            "barcode": "3038401022657083",
            "last_name": "Test"
        }
        resp = self.client.post(reverse('membership-cards'), data=payload, **self.auth_headers)
        self.assertIn('membership plan not allowed', resp.json()['detail'])

    @httpretty.activate
    def test_membership_card_transactions(self):
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

    def test_composite_payment_card_get(self):
        resp = self.client.get(reverse('composite-payment-cards', args=[self.scheme_account.id]),
                               **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

    @patch('intercom.intercom_api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_composite_payment_card_post(self, *_):
        new_sa = SchemeAccountEntryFactory(user=self.user).scheme_account
        payload = {
            "card": {
                "pan_end": 1234,
                "currency_code": "GBP",
                "pan_start": 123456,
                "issuer": self.payment_card_account_entry.payment_card_account.issuer.id,
                "payment_card": self.payment_card_account_entry.payment_card_account.payment_card.id,
                "name_on_card": "test user composite",
                "token": "abc2",
                "fingerprint": "qwertyuioplkjhhgfdsa",
                "expiry_year": 22,
                "expiry_month": 3,
                "country": "UK",
                "order": 1
            },
            "consent": {
                "latitude": 51.405372,
                "longitude": -0.678357,
                "timestamp": 1517549941
            }
        }
        expected_links = [
            {
                'id': new_sa.id,
                'name': str(new_sa),
                'active_link': True
            }
        ]

        resp = self.client.post(reverse('composite-payment-cards', args=[new_sa.id]), data=json.dumps(payload),
                                content_type='application/json', **self.auth_headers)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(expected_links, resp.json()['membership_cards'])

    def test_composite_membership_card_get(self):
        resp = self.client.get(reverse('composite-membership-cards', args=[self.payment_card_account.id]),
                               **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

    @patch('intercom.intercom_api')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_composite_membership_card_post(self, mock_get_midas_balance, *_):
        new_pca = PaymentCardAccountEntryFactory(user=self.user).payment_card_account
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'reward_tier': 0,
            'balance': Decimal('20'),
            'is_stale': False
        }
        payload = {
            "order": 1,
            "membership_plan": self.scheme.id,
            "barcode": "1234401022657083",
            "last_name": "Test Composite"
        }
        expected_links = [
            {
                'id': new_pca.id,
                'name': str(new_pca),
                'active_link': True
            }
        ]

        resp = self.client.post(reverse('composite-membership-cards', args=[new_pca.id]), data=payload,
                                **self.auth_headers)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(expected_links, resp.json()['payment_cards'])

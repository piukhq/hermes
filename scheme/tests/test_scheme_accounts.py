import datetime
import json
import secrets
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList

from scheme.credentials import (ADDRESS_1, ADDRESS_2, BARCODE, CARD_NUMBER, CREDENTIAL_TYPES, EMAIL, FIRST_NAME,
                                LAST_NAME, PASSWORD, PHONE, TITLE, TOWN_CITY, USER_NAME)
from scheme.encyption import AESCipher
from scheme.models import (ConsentStatus, JourneyTypes, Scheme, SchemeAccount, SchemeAccountCredentialAnswer,
                           SchemeCredentialQuestion, UserConsent)
from scheme.serializers import LinkSchemeSerializer, ListSchemeAccountSerializer, ResponseLinkSerializer
from scheme.tests.factories import (ConsentFactory, ExchangeFactory, SchemeAccountFactory, SchemeAccountImageFactory,
                                    SchemeCredentialAnswerFactory, SchemeCredentialQuestionFactory, SchemeFactory,
                                    SchemeImageFactory,
                                    UserConsentFactory)
from scheme.views import UpdateSchemeAccountStatus
from ubiquity.models import SchemeAccountEntry
from ubiquity.tests.factories import SchemeAccountEntryFactory
from user.models import Setting
from user.tests.factories import SettingFactory, UserFactory, UserSettingFactory


class TestSchemeAccountViews(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheme = SchemeFactory()
        cls.scheme_image = SchemeImageFactory(scheme=cls.scheme)
        SchemeCredentialQuestionFactory(scheme=cls.scheme,
                                        type=USER_NAME,
                                        manual_question=True)
        secondary_question = SchemeCredentialQuestionFactory(scheme=cls.scheme,
                                                             type=CARD_NUMBER,
                                                             third_party_identifier=True,
                                                             options=SchemeCredentialQuestion.LINK)
        password_question = SchemeCredentialQuestionFactory(scheme=cls.scheme,
                                                            type=PASSWORD,
                                                            options=SchemeCredentialQuestion.LINK_AND_JOIN)

        cls.scheme_account = SchemeAccountFactory(scheme=cls.scheme)
        cls.scheme_account_answer = SchemeCredentialAnswerFactory(question=cls.scheme.manual_question,
                                                                  scheme_account=cls.scheme_account)
        cls.second_scheme_account_answer = SchemeCredentialAnswerFactory(question=secondary_question,
                                                                         scheme_account=cls.scheme_account)

        cls.scheme_account_answer_password = SchemeCredentialAnswerFactory(answer="test_password",
                                                                           question=password_question,
                                                                           scheme_account=cls.scheme_account)
        cls.consent = ConsentFactory.create(
            scheme=cls.scheme,
            slug=secrets.token_urlsafe()
        )
        metadata1 = {'journey': JourneyTypes.LINK.value}
        metadata2 = {'journey': JourneyTypes.JOIN.value}
        cls.scheme_account_consent1 = UserConsentFactory(scheme_account=cls.scheme_account, metadata=metadata1,
                                                         status=ConsentStatus.PENDING)
        cls.scheme_account_consent2 = UserConsentFactory(scheme_account=cls.scheme_account, metadata=metadata2,
                                                         status=ConsentStatus.SUCCESS)

        cls.scheme1 = SchemeFactory(card_number_regex=r'(^[0-9]{16})', card_number_prefix='', tier=Scheme.PLL)
        cls.scheme_account1 = SchemeAccountFactory(scheme=cls.scheme1)
        barcode_question = SchemeCredentialQuestionFactory(scheme=cls.scheme1,
                                                           type=BARCODE,
                                                           options=SchemeCredentialQuestion.LINK)
        SchemeCredentialQuestionFactory(scheme=cls.scheme1, type=CARD_NUMBER, third_party_identifier=True)
        cls.scheme_account_answer_barcode = SchemeCredentialAnswerFactory(answer="9999888877776666",
                                                                          question=barcode_question,
                                                                          scheme_account=cls.scheme_account1)
        cls.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=cls.scheme_account)
        SchemeAccountEntryFactory(scheme_account=cls.scheme_account1)
        cls.user = cls.scheme_account_entry.user

        cls.scheme.save()
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        cls.auth_service_headers = {'HTTP_AUTHORIZATION': 'Token ' + settings.SERVICE_API_KEY}

        cls.scheme_account_image = SchemeAccountImageFactory()

        super().setUpClass()

    def test_scheme_account_query(self):
        resp = self.client.get('/schemes/accounts/query?scheme__slug={}&user_set__id={}'.format(self.scheme.slug,
                                                                                                self.user.id),
                               **self.auth_service_headers)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json()[0]['id'], self.scheme_account.id)

    def test_scheme_account_bad_query(self):
        resp = self.client.get('/schemes/accounts/query?scheme=what&user=no', **self.auth_service_headers)
        self.assertEqual(400, resp.status_code)

    def test_scheme_account_query_no_results(self):
        resp = self.client.get('/schemes/accounts/query?scheme__slug=scheme-that-doesnt-exist',
                               **self.auth_service_headers)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(0, len(resp.json()))

    @patch('analytics.api._send_to_mnemosyne')
    def test_join_account(self, mock_send_to_mnemosyne):
        join_scheme = SchemeFactory()
        question = SchemeCredentialQuestionFactory(scheme=join_scheme, type=USER_NAME, manual_question=True)
        join_account = SchemeAccountFactory(scheme=join_scheme, status=SchemeAccount.JOIN)
        SchemeAccountEntryFactory(scheme_account=join_account, user=self.user)

        response = self.client.post('/schemes/accounts', data={
            'scheme': join_scheme.id,
            'order': 0,
            question: 'test',
        }, **self.auth_headers)

        self.assertEqual(response.status_code, 201)

        data = response.json()
        self.assertEqual(data['id'], join_account.id)
        self.assertEqual(data['order'], 0)
        self.assertEqual(data['scheme'], join_scheme.id)
        self.assertEqual(data['username'], 'test')
        self.assertTrue(mock_send_to_mnemosyne.called)

    @patch('analytics.api._send_to_mnemosyne')
    def test_join_account_with_error_join_card(self, mock_send_to_mnemosyne):
        join_scheme = SchemeFactory()
        question = SchemeCredentialQuestionFactory(scheme=join_scheme, type=USER_NAME, manual_question=True)
        join_account = SchemeAccountFactory(scheme=join_scheme, status=SchemeAccount.CARD_NOT_REGISTERED)
        SchemeAccountEntryFactory(scheme_account=join_account, user=self.user)

        response = self.client.post('/schemes/accounts', data={
            'scheme': join_scheme.id,
            'order': 0,
            question: 'test',
        }, **self.auth_headers)

        self.assertEqual(response.status_code, 201)

        data = response.json()
        self.assertEqual(data['id'], join_account.id)
        self.assertEqual(data['order'], 0)
        self.assertEqual(data['scheme'], join_scheme.id)
        self.assertEqual(data['username'], 'test')
        self.assertTrue(mock_send_to_mnemosyne.called)

    def test_get_scheme_account(self):
        response = self.client.get('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.scheme_account.id)
        self.assertIsNone(response.data['barcode'])
        self.assertEqual(response.data['card_label'], self.scheme_account_answer.answer)
        self.assertNotIn('is_deleted', response.data)
        self.assertEqual(response.data['scheme']['id'], self.scheme.id)
        self.assertNotIn('card_number_prefix', response.data['scheme'])
        self.assertEqual(response.data['display_status'], SchemeAccount.ACTIVE)

    @patch('analytics.api.update_attributes')
    @patch('analytics.api._get_today_datetime')
    def test_delete_schemes_account(self, mock_date, mock_update_attr):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        response = self.client.delete('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)

        self.assertEqual(
            mock_update_attr.call_args[0][1],
            {
                '{0}'.format(self.scheme_account.scheme.company):
                    'true,ACTIVE,2000/05/19,{},prev_None,current_ACTIVE'.format(
                    self.scheme_account.scheme.slug)
            }
        )

        deleted_scheme_account = SchemeAccount.all_objects.get(id=self.scheme_account.id)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(deleted_scheme_account.is_deleted)

        response = self.client.get('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)
        response = self.client.post('/schemes/accounts/{0}/link'.format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)

    @patch('analytics.api._get_today_datetime')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_link_schemes_account_no_consents(self, mock_get_midas_balance, mock_date):
        link_scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=link_scheme, type=USER_NAME, manual_question=True)
        SchemeCredentialQuestionFactory(scheme=link_scheme, type=CARD_NUMBER, options=SchemeCredentialQuestion.LINK)
        SchemeCredentialQuestionFactory(scheme=link_scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK)
        link_scheme_account = SchemeAccountFactory(scheme=link_scheme)
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=link_scheme_account)
        SchemeCredentialAnswerFactory(question=link_scheme.manual_question, scheme_account=link_scheme_account)
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'reward_tier': 0,
            'balance': Decimal('20'),
            'is_stale': False
        }

        auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + scheme_account_entry.user.create_token()}
        data = {
            CARD_NUMBER: "London",
            PASSWORD: "sdfsdf",
        }

        response = self.client.post('/schemes/accounts/{0}/link'.format(link_scheme_account.id),
                                    data=data, **auth_headers, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['balance']['points'], '100.00')
        self.assertEqual(response.data['status_name'], "Active")
        self.assertTrue(ResponseLinkSerializer(data=response.data).is_valid())
        self.assertIsNone(response.data.get('barcode'))

    @patch('analytics.api._get_today_datetime')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_link_scheme_account_with_consents(self, mock_get_midas_balance, mock_date):
        link_scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=link_scheme, type=USER_NAME, manual_question=True)
        SchemeCredentialQuestionFactory(scheme=link_scheme, type=BARCODE, options=SchemeCredentialQuestion.LINK)
        link_scheme_account = SchemeAccountFactory(scheme=link_scheme)
        link_scheme_account_entry = SchemeAccountEntryFactory(scheme_account=link_scheme_account)
        SchemeCredentialAnswerFactory(question=link_scheme.manual_question, scheme_account=link_scheme_account)
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'reward_tier': 0,
            'balance': Decimal('20'),
            'is_stale': False
        }

        auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + link_scheme_account_entry.user.create_token()}
        data = {
            BARCODE: "1234567",
        }

        response = self.client.post('/schemes/accounts/{0}/link'.format(link_scheme_account.id),
                                    data=data, **auth_headers, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['balance']['points'], '100.00')
        self.assertEqual(response.data['status_name'], "Active")
        self.assertTrue(ResponseLinkSerializer(data=response.data).is_valid())
        self.assertTrue(response.data.get('barcode'))

    @patch('analytics.api._get_today_datetime')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_link_schemes_account_display_status(self, mock_get_midas_balance, mock_date):
        link_scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=link_scheme, type=USER_NAME, manual_question=True)
        SchemeCredentialQuestionFactory(scheme=link_scheme, type=CARD_NUMBER, options=SchemeCredentialQuestion.LINK)
        SchemeCredentialQuestionFactory(scheme=link_scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK)
        link_scheme_account = SchemeAccountFactory(scheme=link_scheme)
        link_scheme_account_entry = SchemeAccountEntryFactory(scheme_account=link_scheme_account)
        SchemeCredentialAnswerFactory(question=link_scheme.manual_question, scheme_account=link_scheme_account)
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'reward_tier': 0,
            'balance': Decimal('20'),
            'is_stale': False
        }

        auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + link_scheme_account_entry.user.create_token()}
        data = {
            CARD_NUMBER: "London",
            PASSWORD: "sdfsdf",
        }

        response = self.client.post('/schemes/accounts/{0}/link'.format(link_scheme_account.id),
                                    data=data, **auth_headers, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['balance']['points'], '100.00')
        self.assertEqual(response.data['status_name'], "Active")
        self.assertTrue(ResponseLinkSerializer(data=response.data).is_valid())

    @patch('analytics.api.update_attributes')
    @patch('analytics.api._get_today_datetime')
    @patch.object(SchemeAccount, '_get_balance')
    def test_link_schemes_account_error_displays_status(self, mock_get_balance, mock_date, mock_update_attr):
        mappings = [
            {'mock_response': SchemeAccount.ACTIVE, 'expected_display_status': SchemeAccount.ACTIVE},
            {'mock_response': SchemeAccount.END_SITE_DOWN, 'expected_display_status': SchemeAccount.WALLET_ONLY},
            {'mock_response': SchemeAccount.INVALID_CREDENTIALS, 'expected_display_status': SchemeAccount.WALLET_ONLY},
            {'mock_response': SchemeAccount.JOIN, 'expected_display_status': SchemeAccount.JOIN}
        ]

        for item in mappings:
            scheme_account = SchemeAccountFactory(scheme=self.scheme, status=SchemeAccount.WALLET_ONLY)
            scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account)
            SchemeCredentialAnswerFactory(question=self.scheme.manual_question, answer='test',
                                          scheme_account=scheme_account)

            mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
            auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + scheme_account_entry.user.create_token()}
            data = {
                CARD_NUMBER: "1234",
                PASSWORD: "abcd",
            }

            mock_get_balance.return_value.status_code = item['mock_response']
            response = self.client.post('/schemes/accounts/{0}/link'.format(scheme_account.id),
                                        data=data, **auth_headers, format='json')

            self.assertEqual(response.status_code, 201)
            scheme_account.refresh_from_db()
            self.assertEqual(scheme_account.status, item['mock_response'])
            self.assertEqual(response.data['display_status'], item['expected_display_status'])

    @patch('analytics.api.update_attributes')
    @patch('analytics.api._get_today_datetime')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_link_schemes_account_with_consents(self, mock_get_midas_balance, mock_date, mock_update_attr):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'reward_tier': 0,
            'balance': Decimal('20'),
            'is_stale': False
        }

        test_reply = True
        test_reply2 = False
        consent1 = ConsentFactory.create(scheme=self.scheme_account.scheme, slug=secrets.token_urlsafe())
        consent2 = ConsentFactory.create(scheme=self.scheme_account.scheme, slug=secrets.token_urlsafe(),
                                         required=False)

        data = {
            CARD_NUMBER: "London",
            PASSWORD: "sdfsdf",
            "consents": [
                {"id": "{}".format(self.consent.id), "value": test_reply},
                {"id": "{}".format(consent1.id), "value": test_reply},
                {"id": "{}".format(consent2.id), "value": test_reply2}
            ]
        }

        response = self.client.post('/schemes/accounts/{0}/link'.format(self.scheme_account.id),
                                    data=data, **self.auth_headers, format='json')

        set_values = UserConsent.objects.filter(scheme_account=self.scheme_account).values()
        self.assertEqual(len(set_values), 5, "Incorrect number of consents found expected 5")
        saved_consents = [self.consent, consent1, consent2]
        for consent in saved_consents:
            user_consent = UserConsent.objects.get(scheme_account=self.scheme_account, slug=consent.slug)
            self.assertEqual(user_consent.status, ConsentStatus.SUCCESS)
            if consent is consent2:
                self.assertEqual(user_consent.value, test_reply2)
            else:
                self.assertEqual(user_consent.value, test_reply)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['balance']['points'], '100.00')
        self.assertEqual(response.data['status_name'], "Active")
        self.assertTrue(ResponseLinkSerializer(data=response.data).is_valid())
        self.assertIsNone(response.data.get('barcode'))

    @patch('analytics.api._get_today_datetime')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_link_schemes_account_error_deletes_pending_consents(self, mock_get_midas_balance, mock_date,):
        error_scheme_account = SchemeAccountFactory(scheme=self.scheme, status=SchemeAccount.INVALID_CREDENTIALS)
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        mock_get_midas_balance.return_value = None

        metadata = {'journey': JourneyTypes.LINK.value}
        success_scheme_account_user_consent = UserConsentFactory(scheme_account=error_scheme_account, metadata=metadata,
                                                                 status=ConsentStatus.SUCCESS)
        SchemeAccountEntryFactory(scheme_account=error_scheme_account, user=success_scheme_account_user_consent.user)
        UserConsentFactory(scheme_account=error_scheme_account, metadata=metadata, status=ConsentStatus.PENDING)
        test_reply = True
        auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + success_scheme_account_user_consent.user.create_token()}
        data = {
            CARD_NUMBER: "London",
            PASSWORD: "sdfsdf",
            "consents": [
                {"id": "{}".format(self.consent.id), "value": test_reply},
            ]
        }

        response = self.client.post('/schemes/accounts/{0}/link'.format(error_scheme_account.id),
                                    data=data, **auth_headers, format='json')

        self.assertEqual(response.status_code, 201)
        set_values = UserConsent.objects.filter(scheme_account=error_scheme_account).values()
        self.assertEqual(len(set_values), 1, "Incorrect number of consents found expected 1")
        successful_consent = set_values[0]
        self.assertEqual(successful_consent['id'], success_scheme_account_user_consent.id)

    @patch('analytics.api._get_today_datetime')
    @patch.object(SchemeAccount, '_get_balance')
    def test_link_schemes_account_pre_registered_card_error(self, mock_get_balance, mock_date):
        scheme_account = SchemeAccountFactory(scheme=self.scheme, status=SchemeAccount.WALLET_ONLY)
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account)
        SchemeCredentialAnswerFactory(question=self.scheme.manual_question, answer='test',
                                      scheme_account=scheme_account)

        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        mock_get_balance.return_value.status_code = SchemeAccount.PRE_REGISTERED_CARD
        auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + scheme_account_entry.user.create_token()}
        data = {
            CARD_NUMBER: "1234",
            PASSWORD: "abcd",
        }

        current_credentials = SchemeAccountCredentialAnswer.objects.filter(scheme_account=scheme_account.id)
        self.assertEqual(len(current_credentials), 1)
        response = self.client.post('/schemes/accounts/{0}/link'.format(scheme_account.id),
                                    data=data, **auth_headers, format='json')

        self.assertEqual(response.status_code, 201)
        scheme_account.refresh_from_db()
        self.assertEqual(scheme_account.status, SchemeAccount.PRE_REGISTERED_CARD)
        self.assertEqual(scheme_account.display_status, SchemeAccount.JOIN)
        credentials = SchemeAccountCredentialAnswer.objects.filter(scheme_account=scheme_account.id)
        self.assertEqual(len(credentials), 0)

    def test_list_schemes_accounts(self):
        response = self.client.get('/schemes/accounts', **self.auth_headers)
        self.assertEqual(type(response.data), ReturnList)
        self.assertEqual(response.data[0]['scheme']['name'], self.scheme.name)
        self.assertEqual(response.data[0]['status_name'], 'Active')
        self.assertIn('barcode', response.data[0])
        self.assertIn('card_label', response.data[0])
        self.assertNotIn('barcode_regex', response.data[0]['scheme'])
        expected_transaction_headers = [{"name": "header 1"}, {"name": "header 2"}, {"name": "header 3"}]
        self.assertListEqual(expected_transaction_headers, response.data[0]['scheme']["transaction_headers"])

    @patch('analytics.api.update_attributes')
    @patch('analytics.api._get_today_datetime')
    def test_wallet_only(self, mock_date, mock_update_attr):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)

        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER, manual_question=True)

        response = self.client.post('/schemes/accounts', data={'scheme': scheme.id, CARD_NUMBER: '1234', 'order': 0},
                                    **self.auth_headers)
        self.assertEqual(response.status_code, 201)
        content = response.data
        self.assertEqual(content['scheme'], scheme.id)
        self.assertEqual(content['card_number'], '1234')
        self.assertIn('/schemes/accounts/', response._headers['location'][1])
        self.assertEqual(SchemeAccount.objects.get(pk=content['id']).status, SchemeAccount.WALLET_ONLY)

        self.assertEqual(
            mock_update_attr.call_args[0][1],
            {
                '{0}'.format(scheme.company):
                    'false,WALLET_ONLY,2000/05/19,{},prev_None,current_WALLET_ONLY'.format(scheme.slug)
            }
        )

    @patch('scheme.views.UpdateSchemeAccountStatus.notify_rollback_transactions')
    def test_scheme_account_update_status(self, mock_notify_rollback):
        data = {
            'status': 9,
            'journey': 'join'
        }
        response = self.client.post('/schemes/accounts/{}/status/'.format(self.scheme_account.id), data=data,
                                    **self.auth_service_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.scheme_account.id)
        self.assertEqual(response.data['status'], 9)
        self.assertFalse(mock_notify_rollback.called)

    def test_scheme_account_update_status_bad(self):
        response = self.client.post('/schemes/accounts/{}/status/'.format(self.scheme_account.id),
                                    data={
                                        'status': 112,
                                        'journey': None
                                    },
                                    **self.auth_service_headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, ['Invalid status code sent.'])

    @patch('scheme.views.UpdateSchemeAccountStatus.notify_rollback_transactions')
    def test_scheme_account_status_rollback_transactions_update(self, mock_notify_rollback):
        data = {
            'status': 1,
            'journey': 'join'
        }
        response = self.client.post('/schemes/accounts/{}/status/'.format(self.scheme_account1.id), data=data,
                                    **self.auth_service_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.scheme_account1.id)
        self.assertEqual(response.data['status'], 1)
        self.assertTrue(mock_notify_rollback.called)

    @patch('scheme.views.sentry')
    @patch('scheme.views.requests.post')
    def test_notify_join_for_rollback_transactions(self, mock_post, mock_sentry):
        UpdateSchemeAccountStatus.notify_rollback_transactions('harvey-nichols', self.scheme_account,
                                                               datetime.datetime.now())

        self.assertFalse(mock_sentry.captureException.called)
        self.assertTrue(mock_post.called)

    def test_scheme_accounts_active(self):
        scheme = SchemeAccountFactory(status=SchemeAccount.ACTIVE)
        scheme_2 = SchemeAccountFactory(status=SchemeAccount.END_SITE_DOWN)
        response = self.client.get('/schemes/accounts/active', **self.auth_service_headers)

        self.assertEqual(response.status_code, 200)
        scheme_ids = [result['id'] for result in response.data['results']]
        self.assertIsNone(response.data['next'])
        self.assertIn(scheme.id, scheme_ids)
        self.assertNotIn('credentials', response.data['results'][0])
        self.assertNotIn('scheme', response.data['results'][0])
        self.assertNotIn(scheme_2.id, scheme_ids)

    def test_system_retry_scheme_accounts(self):
        scheme = SchemeAccountFactory(status=SchemeAccount.RETRY_LIMIT_REACHED)
        scheme_2 = SchemeAccountFactory(status=SchemeAccount.ACTIVE)
        response = self.client.get('/schemes/accounts/system_retry', **self.auth_service_headers)
        scheme_ids = [result['id'] for result in response.data['results']]

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['next'])
        self.assertIn(scheme.id, scheme_ids)
        self.assertNotIn(scheme_2.id, scheme_ids)

    def test_get_scheme_accounts_credentials(self):
        response = self.client.get('/schemes/accounts/{0}/credentials'.format(self.scheme_account.id),
                                   **self.auth_service_headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('credentials', response.data)
        self.assertIn('scheme', response.data)
        self.assertIn('display_status', response.data)
        self.assertIn('status_name', response.data)
        self.assertIn('id', response.data)

    def test_get_scheme_accounts_credentials_user(self):
        response = self.client.get('/schemes/accounts/{0}/credentials'.format(self.scheme_account.id),
                                   **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('id', response.data)

    def test_scheme_account_collect_credentials(self):
        self.assertEqual(self.scheme_account._collect_credentials(), {
            'card_number': self.second_scheme_account_answer.answer, 'password': 'test_password',
            'username': self.scheme_account_answer.answer})

    def test_scheme_account_collect_credentials_with_merchant_identifier(self):
        third_question = SchemeCredentialQuestionFactory(scheme=self.scheme, type=TITLE,
                                                         options=SchemeCredentialQuestion.MERCHANT_IDENTIFIER)
        SchemeCredentialAnswerFactory(question=third_question, answer='mr', scheme_account=self.scheme_account)

        self.assertEqual(self.scheme_account._collect_credentials(), {
            'card_number': self.second_scheme_account_answer.answer,
            'password': 'test_password',
            'username': self.scheme_account_answer.answer,
            'title': 'mr'
        })

    def test_scheme_account_collect_pending_consents(self):
        consents = self.scheme_account.collect_pending_consents()

        self.assertEqual(len(consents), 1)
        expected_keys = {'id', 'slug', 'value', 'created_on', 'journey_type'}
        consent = consents[0]
        self.assertEqual(set(consent.keys()), expected_keys)
        self.assertEqual(consent['id'], self.scheme_account_consent1.id)

    def test_scheme_account_collect_pending_consents_no_data(self):
        self.assertEqual(self.scheme_account1.collect_pending_consents(), [])

    def test_scheme_account_third_party_identifier(self):
        self.assertEqual(self.scheme_account.third_party_identifier, self.second_scheme_account_answer.answer)
        self.assertEqual(self.scheme_account1.third_party_identifier, self.scheme_account_answer_barcode.answer)

    def test_scheme_account_encrypted_credentials(self):
        decrypted_credentials = json.loads(AESCipher(settings.AES_KEY.encode()).decrypt(
            self.scheme_account.credentials()))

        self.assertEqual(decrypted_credentials['card_number'], self.second_scheme_account_answer.answer)
        self.assertEqual(decrypted_credentials['password'], 'test_password')
        self.assertEqual(decrypted_credentials['username'], self.scheme_account_answer.answer)

        consents = decrypted_credentials['consents']
        self.assertEqual(len(consents), 1)
        expected_keys = {'id', 'slug', 'value', 'created_on', 'journey_type'}
        for consent in consents:
            self.assertEqual(set(consent.keys()), expected_keys)

    def test_scheme_account_encrypted_credentials_bad(self):
        scheme_account = SchemeAccountFactory(scheme=self.scheme)
        SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)
        encrypted_credentials = scheme_account.credentials()
        self.assertIsNone(encrypted_credentials)
        self.assertEqual(scheme_account.status, SchemeAccount.INCOMPLETE)

    def test_temporary_iceland_fix_ignores_credential_validation_for_iceland(self):
        scheme = SchemeFactory(slug='iceland-bonus-card')
        SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE, manual_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK)
        scheme_account = SchemeAccountFactory(scheme=scheme)

        self.assertIsNotNone(scheme_account.credentials(), {})

    def test_temporary_iceland_fix_credential_validation_for_not_iceland(self):
        scheme = SchemeFactory(slug='not-iceland')
        SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE, manual_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK)
        scheme_account = SchemeAccountFactory(scheme=scheme)

        self.assertIsNone(scheme_account.credentials())

    def test_scheme_account_answer_serializer(self):
        """
        If this test breaks you need to add the new credential to the SchemeAccountAnswerSerializer
        """
        expected_fields = dict(CREDENTIAL_TYPES)
        expected_fields['consents'] = None  # Add consents
        self.assertEqual(set(expected_fields.keys()),
                         set(LinkSchemeSerializer._declared_fields.keys())
                         )

    def test_scheme_account_summary(self):
        response = self.client.get('/schemes/accounts/summary', **self.auth_service_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnList)
        self.assertTrue(len(response.data) > 0)
        self.assertTrue(self.all_statuses_correct(response.data))

    def all_statuses_correct(self, scheme_list):
        status_dict = dict(SchemeAccount.STATUSES)
        for scheme in scheme_list:
            scheme_status_codes = [int(s['status']) for s in scheme['statuses']]
            for status_code in status_dict:
                if status_code not in scheme_status_codes:
                    return False
        return True

    @patch('analytics.api.post_event')
    @patch('analytics.api._get_today_datetime')
    @patch('analytics.api.update_attributes')
    @patch('analytics.api._send_to_mnemosyne')
    def test_create_join_account_and_notify_analytics(self, mock_post_event, mock_date, mock_update_attributes,
                                                      mock_send_to_mnemosyne):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        scheme = SchemeFactory()

        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, manual_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD)

        resp = self.client.post('/schemes/accounts/join/{}/{}'.format(scheme.slug, self.user.id),
                                **self.auth_service_headers)

        self.assertEqual(resp.status_code, 201)

        json = resp.json()
        self.assertIsInstance(json, dict)
        self.assertIn('display_status', json)
        self.assertIn('barcode', json)
        self.assertIn('card_label', json)
        self.assertIn('created', json)
        self.assertIn('id', json)
        self.assertIn('images', json)
        self.assertIn('order', json)
        self.assertIn('scheme', json)
        self.assertIn('status', json)

        self.assertEqual(mock_post_event.call_count, 1)
        self.assertEqual(len(mock_post_event.call_args), 2)
        self.assertEqual(mock_update_attributes.call_count, 1)

    @patch('analytics.api.post_event')
    @patch('analytics.api.update_attributes')
    def test_create_join_account_against_user_setting(self, mock_update_attr, mock_post_event):
        scheme = SchemeFactory()

        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, manual_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD)

        setting = SettingFactory(scheme=scheme, slug='join-{}'.format(scheme.slug), value_type=Setting.BOOLEAN)
        UserSettingFactory(setting=setting, user=self.user, value='0')

        resp = self.client.post('/schemes/accounts/join/{}/{}'.format(scheme.slug, self.user.id),
                                **self.auth_service_headers)

        self.assertEqual(resp.status_code, 200)

        json = resp.json()
        self.assertEqual(json['code'], 200)
        self.assertEqual(json['message'], 'User has disabled join cards for this scheme')

        self.assertFalse(mock_post_event.called)
        self.assertFalse(mock_update_attr.called)

    def test_register_join_endpoint_missing_credential_question(self):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK_AND_JOIN)

        data = {
            'save_user_information': False,
            'order': 2,
            'password': 'password'
        }
        resp = self.client.post('/schemes/{}/join'.format(scheme.id), **self.auth_headers, data=data)

        self.assertEqual(resp.status_code, 400)
        json = resp.json()
        self.assertEqual(json, {'non_field_errors': ['username field required']})

    def test_register_join_endpoint_missing_save_user_information(self):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK_AND_JOIN)

        data = {
            'order': 2,
            'username': 'testbink',
            'password': 'password'

        }
        resp = self.client.post('/schemes/{}/join'.format(scheme.id), **self.auth_headers, data=data)

        self.assertEqual(resp.status_code, 400)
        json = resp.json()
        self.assertEqual(json, {'save_user_information': ['This field is required.']})

    def test_register_join_endpoint_scheme_has_no_join_questions(self):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER, options=SchemeCredentialQuestion.LINK)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK)

        data = {
            'order': 2,
            'save_user_information': False,
            'username': 'testbink',
            'password': 'password'

        }
        resp = self.client.post('/schemes/{}/join'.format(scheme.id), **self.auth_headers, data=data)

        self.assertEqual(resp.status_code, 400)
        json = resp.json()
        self.assertEqual(json, {'non_field_errors': ['No join questions found for scheme: {}'.format(scheme.slug)]})

    def test_register_join_endpoint_account_already_created(self):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.JOIN)
        sa = SchemeAccountFactory(scheme_id=scheme.id)
        SchemeAccountEntryFactory(user=self.user, scheme_account=sa)

        data = {
            'save_user_information': False,
            'order': 2,
            'username': 'testbink',
            'password': 'password'

        }
        resp = self.client.post('/schemes/{}/join'.format(scheme.id), **self.auth_headers, data=data)
        self.assertEqual(resp.status_code, 400)
        json = resp.json()
        self.assertTrue(json['non_field_errors'][0].startswith('You already have an account for this scheme'))

    def test_register_join_endpoint_link_join_question_mismatch(self):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER, options=SchemeCredentialQuestion.LINK)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.JOIN)

        data = {
            'save_user_information': False,
            'order': 2,
            'username': 'testbink',
            'password': 'password'

        }
        resp = self.client.post('/schemes/{}/join'.format(scheme.id), **self.auth_headers, data=data)
        self.assertEqual(resp.status_code, 400)
        json = resp.json()
        self.assertTrue(json['non_field_errors'][0].startswith('Please convert all \"Link\" only credential'
                                                               ' questions to \"Join & Link\"'))

    @patch('requests.post', auto_spec=True, return_value=MagicMock())
    def test_register_join_endpoint_create_scheme_account(self, mock_request):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {'message': 'success'}

        scheme = SchemeFactory()
        link_question = SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, manual_question=True,
                                                        options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE, options=SchemeCredentialQuestion.OPTIONAL_JOIN)

        test_reply = 1
        consent1 = ConsentFactory.create(
            scheme=scheme,
            journey=JourneyTypes.JOIN.value,
            order=1
        )

        data = {
            'save_user_information': False,
            'order': 2,
            'username': 'testbink',
            'password': 'password',
            'barcode': 'barcode',
            "consents": [{"id": "{}".format(consent1.id), "value": test_reply}]
        }
        resp = self.client.post('/schemes/{}/join'.format(scheme.id), **self.auth_headers, data=data, format='json')

        new_scheme_account = SchemeAccountEntry.objects.get(
            user=self.user, scheme_account__scheme=scheme).scheme_account

        set_values = UserConsent.objects.filter(scheme_account=new_scheme_account).values()
        self.assertEqual(len(set_values), 1, "Incorrect number of consents found expected 1")
        for set_value in set_values:
            if set_value['slug'] == consent1.slug:
                self.assertEqual(set_value['value'], test_reply, "Incorrect Consent value set")
            else:
                self.assertTrue(False, "Consent not set")

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(mock_request.called)

        resp_json = resp.json()
        self.assertEqual(resp_json['scheme'], scheme.id)
        self.assertEqual(len(resp_json), len(data))  # not +1 to data since consents have been added
        scheme_account = SchemeAccount.objects.get(user_set__id=self.user.id, scheme_id=scheme.id)
        self.assertEqual(resp_json['id'], scheme_account.id)
        self.assertEqual('Pending', scheme_account.status_name)
        self.assertEqual(len(scheme_account.schemeaccountcredentialanswer_set.all()), 1)
        self.assertTrue(scheme_account.schemeaccountcredentialanswer_set.filter(question=link_question))

    @patch('requests.post', auto_spec=True, return_value=MagicMock())
    def test_register_join_endpoint_optional_join_not_required(self, mock_request):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {'message': 'success'}

        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.OPTIONAL_JOIN)

        data = {
            'save_user_information': False,
            'order': 2,
            'username': 'testbink',
        }
        resp = self.client.post('/schemes/{}/join'.format(scheme.id), **self.auth_headers, data=data)
        self.assertEqual(resp.status_code, 201)

    @patch('requests.post', auto_spec=True, return_value=MagicMock())
    def test_register_join_endpoint_saves_user_profile(self, mock_request):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {'message': 'success'}

        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=EMAIL, manual_question=True,
                                        options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PHONE, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=TITLE, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=FIRST_NAME, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=LAST_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=ADDRESS_1, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=ADDRESS_2, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=TOWN_CITY, options=SchemeCredentialQuestion.JOIN)

        phone_number = '01234567890'
        title = 'mr'
        first_name = 'bob'
        last_name = 'test'
        address_1 = '1 ascot road'
        address_2 = 'caversham'
        town_city = 'ascot'
        data = {
            'save_user_information': True,
            'order': 2,
            'username': 'testbink',
            'password': 'password',
            'email': 'test@testbink.com',
            'phone': phone_number,
            'title': title,
            'first_name': first_name,
            'last_name': last_name,
            'address_1': address_1,
            'address_2': address_2,
            'town_city': town_city,
        }
        resp = self.client.post('/schemes/{}/join'.format(scheme.id), **self.auth_headers, data=data)
        self.assertEqual(resp.status_code, 201)

        user = SchemeAccountEntry.objects.filter(scheme_account__scheme=scheme, user=self.user).first().user
        user_profile = user.profile
        self.assertEqual(user_profile.phone, phone_number)
        self.assertEqual(user_profile.first_name, first_name)
        self.assertEqual(user_profile.last_name, last_name)
        self.assertEqual(user_profile.address_line_1, address_1)
        self.assertEqual(user_profile.address_line_2, address_2)
        self.assertEqual(user_profile.city, town_city)

    @patch('requests.post', auto_spec=True, return_value=MagicMock())
    def test_register_join_endpoint_set_scheme_status_to_join_on_fail(self, mock_request):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {'message': 'fail'}

        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme,
                                        type=USER_NAME,
                                        manual_question=True,
                                        options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.JOIN)
        consent = ConsentFactory(scheme=scheme)

        data = {
            'save_user_information': False,
            'order': 2,
            'username': 'testbink',
            'password': 'password',
            'consents': [
                {
                    "id": consent.id,
                    "value": True
                }
            ]

        }

        resp = self.client.post('/schemes/{}/join'.format(scheme.id), **self.auth_headers, data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_request.called)

        resp_json = resp.json()
        self.assertIn('Unknown error with join', resp_json['message'])
        sae = SchemeAccountEntry.objects.get(user=self.user, scheme_account__scheme__id=scheme.id)
        self.assertEqual(sae.scheme_account.status_name, 'Join')
        with self.assertRaises(SchemeAccountCredentialAnswer.DoesNotExist):
            SchemeAccountCredentialAnswer.objects.get(scheme_account_id=sae.scheme_account.id)
        with self.assertRaises(UserConsent.DoesNotExist):
            UserConsent.objects.get(scheme_account_id=sae.scheme_account.id)

    def test_update_user_consent(self):
        user_consent = UserConsentFactory(status=ConsentStatus.PENDING)
        data = {'status': ConsentStatus.SUCCESS.value}

        resp = self.client.put('/schemes/user_consent/{}'.format(user_consent.id), **self.auth_service_headers,
                               data=data)
        self.assertEqual(resp.status_code, 200)
        user_consent.refresh_from_db()
        self.assertEqual(user_consent.status, ConsentStatus.SUCCESS)

    def test_update_user_consents_with_failed_deletes_consent(self):
        user_consent = UserConsentFactory(status=ConsentStatus.SUCCESS)
        data = {'status': ConsentStatus.FAILED.value}

        resp = self.client.put('/schemes/user_consent/{}'.format(user_consent.id), **self.auth_service_headers,
                               data=data)
        self.assertEqual(resp.status_code, 400)
        user_consent.refresh_from_db()
        self.assertEqual(user_consent.status, ConsentStatus.SUCCESS)

    def test_update_user_consents_cant_delete_success_consent(self):
        user_consent = UserConsentFactory(status=ConsentStatus.SUCCESS)
        data = {'status': ConsentStatus.FAILED.value}

        resp = self.client.put('/schemes/user_consent/{}'.format(user_consent.id), **self.auth_service_headers,
                               data=data)
        self.assertEqual(resp.status_code, 400)
        user_consent.refresh_from_db()
        self.assertEqual(user_consent.status, ConsentStatus.SUCCESS)

    def test_update_user_consents_cant_update_success_consent(self):
        user_consent = UserConsentFactory(status=ConsentStatus.SUCCESS)
        data = {'status': ConsentStatus.PENDING.value}

        resp = self.client.put('/schemes/user_consent/{}'.format(user_consent.id), **self.auth_service_headers,
                               data=data)
        self.assertEqual(resp.status_code, 400)
        user_consent.refresh_from_db()
        self.assertEqual(user_consent.status, ConsentStatus.SUCCESS)


class TestSchemeAccountModel(APITestCase):
    def test_missing_credentials(self):
        scheme_account = SchemeAccountFactory()
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=PASSWORD,
                                        options=SchemeCredentialQuestion.LINK)
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=CARD_NUMBER, scan_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=BARCODE, manual_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=TITLE,
                                        options=SchemeCredentialQuestion.MERCHANT_IDENTIFIER)
        self.assertEqual(scheme_account.missing_credentials([]), {BARCODE, PASSWORD, CARD_NUMBER})
        self.assertFalse(scheme_account.missing_credentials([CARD_NUMBER, PASSWORD]))
        self.assertFalse(scheme_account.missing_credentials([BARCODE, PASSWORD]))
        self.assertEqual(scheme_account.missing_credentials([PASSWORD]), {BARCODE, CARD_NUMBER})

    def test_missing_credentials_same_manual_and_scan(self):
        scheme_account = SchemeAccountFactory()
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=BARCODE,
                                        scan_question=True, manual_question=True)
        self.assertFalse(scheme_account.missing_credentials([BARCODE]))
        self.assertEqual(scheme_account.missing_credentials([]), {BARCODE})

    def test_missing_credentials_with_join_option_on_manual_question(self):
        scheme_account = SchemeAccountFactory()
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=BARCODE,
                                        manual_question=True, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=CARD_NUMBER,
                                        scan_question=True, options=SchemeCredentialQuestion.NONE)
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=PASSWORD,
                                        options=SchemeCredentialQuestion.LINK)
        self.assertFalse(scheme_account.missing_credentials([BARCODE, PASSWORD]))
        self.assertFalse(scheme_account.missing_credentials([CARD_NUMBER, PASSWORD]))
        self.assertFalse(scheme_account.missing_credentials([BARCODE, CARD_NUMBER, PASSWORD]))
        self.assertFalse(scheme_account.missing_credentials([BARCODE, CARD_NUMBER, PASSWORD]))
        self.assertEqual(scheme_account.missing_credentials([PASSWORD]), {BARCODE, CARD_NUMBER})

    def test_missing_credentials_with_join_option_on_manual_and_scan_question(self):
        scheme_account = SchemeAccountFactory()
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=BARCODE, manual_question=True,
                                        scan_question=True, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=PASSWORD,
                                        options=SchemeCredentialQuestion.LINK)
        self.assertFalse(scheme_account.missing_credentials([BARCODE, PASSWORD]))
        self.assertEqual(scheme_account.missing_credentials([PASSWORD]), {BARCODE})
        self.assertEqual(scheme_account.missing_credentials([BARCODE]), {PASSWORD})

    def test_credential_check_for_pending_scheme_account(self):
        scheme_account = SchemeAccountFactory(status=SchemeAccount.PENDING)
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=BARCODE, manual_question=True)
        scheme_account.credentials()
        # We expect pending scheme accounts to be missing manual question
        self.assertNotEqual(scheme_account.status, SchemeAccount.INCOMPLETE)

    def test_card_label_from_regex(self):
        scheme = SchemeFactory(card_number_regex='^[0-9]{3}([0-9]+)', card_number_prefix='98263000')
        scheme_account = SchemeAccountFactory(scheme=scheme)
        SchemeCredentialAnswerFactory(question=SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE),
                                      answer='29930842203039', scheme_account=scheme_account)
        self.assertEqual(scheme_account.card_label, '9826300030842203039')

    def test_card_label_from_manual_answer(self):
        question = SchemeCredentialQuestionFactory(type=EMAIL, manual_question=True)
        scheme_account = SchemeAccountFactory(scheme=question.scheme)
        SchemeCredentialAnswerFactory(question=question, answer='frank@sdfg.com', scheme_account=scheme_account)
        self.assertEqual(scheme_account.card_label, 'frank@sdfg.com')

    def test_card_label_from_barcode(self):
        question = SchemeCredentialQuestionFactory(type=BARCODE)
        scheme_account = SchemeAccountFactory(scheme=question.scheme)
        SchemeCredentialAnswerFactory(question=question, answer='49932498', scheme_account=scheme_account)
        self.assertEqual(scheme_account.card_label, '49932498')

    def test_card_label_none(self):
        question = SchemeCredentialQuestionFactory(type=BARCODE)
        scheme_account = SchemeAccountFactory(scheme=question.scheme)
        self.assertIsNone(scheme_account.card_label)

    def test_barcode_from_barcode(self):
        question = SchemeCredentialQuestionFactory(type=BARCODE)
        scheme_account = SchemeAccountFactory(scheme=question.scheme)
        SchemeCredentialAnswerFactory(question=question, answer='49932498', scheme_account=scheme_account)
        self.assertEqual(scheme_account.barcode, '49932498')

    def test_barcode_from_card_number(self):
        scheme = SchemeFactory(barcode_regex='^634004([0-9]+)', barcode_prefix='9794')
        scheme_account = SchemeAccountFactory(scheme=scheme)
        SchemeCredentialAnswerFactory(question=SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER),
                                      answer='634004025035765504', scheme_account=scheme_account)
        self.assertEqual(scheme_account.barcode, '9794025035765504')

    def test_barcode_none(self):
        question = SchemeCredentialQuestionFactory(type=BARCODE)
        scheme_account = SchemeAccountFactory(scheme=question.scheme)
        self.assertIsNone(scheme_account.barcode)

    @patch.object(SchemeAccount, 'credentials', auto_spec=True, return_value=None)
    def test_get_midas_balance_no_credentials(self, mock_credentials):
        entry = SchemeAccountEntryFactory()
        scheme_account = entry.scheme_account
        points = scheme_account.get_midas_balance(JourneyTypes.UPDATE)
        self.assertIsNone(points)
        self.assertTrue(mock_credentials.called)

    @patch('requests.get', auto_spec=True, return_value=MagicMock())
    def test_get_midas_balance(self, mock_request):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {'points': 500}
        entry = SchemeAccountEntryFactory()
        scheme_account = entry.scheme_account
        points = scheme_account.get_midas_balance(JourneyTypes.UPDATE)
        self.assertEqual(points['points'], 500)
        self.assertFalse(points['is_stale'])
        self.assertEqual(scheme_account.status, SchemeAccount.ACTIVE)

    @patch('requests.get', auto_spec=True, side_effect=ConnectionError)
    def test_get_midas_balance_connection_error(self, mock_request):
        entry = SchemeAccountEntryFactory()
        scheme_account = entry.scheme_account
        points = scheme_account.get_midas_balance(JourneyTypes.UPDATE)
        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account.status, SchemeAccount.MIDAS_UNREACHABLE)

    @patch('requests.get', auto_spec=True, return_value=MagicMock())
    def test_get_midas_balance_invalid_status(self, mock_request):
        invalid_status = 502
        mock_request.return_value.status_code = invalid_status
        scheme_account = SchemeAccountFactory()
        points = scheme_account.get_midas_balance(JourneyTypes.UPDATE)

        # check this status hasn't been added to scheme account status
        self.assertNotIn(invalid_status, [status[0] for status in SchemeAccount.EXTENDED_STATUSES])

        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account.status, SchemeAccount.UNKNOWN_ERROR)

    @patch('requests.get', auto_spec=True, return_value=MagicMock())
    def test_get_midas_balance_link_limit_exceeded(self, mock_request):
        test_status = SchemeAccount.LINK_LIMIT_EXCEEDED
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        points = scheme_account.get_midas_balance(JourneyTypes.UPDATE)

        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account.status, test_status)
        self.assertEqual(scheme_account.display_status, scheme_account.WALLET_ONLY)

    @patch('requests.get', auto_spec=True, return_value=MagicMock())
    def test_get_midas_balance_card_not_registered(self, mock_request):
        test_status = SchemeAccount.CARD_NOT_REGISTERED
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        points = scheme_account.get_midas_balance(JourneyTypes.UPDATE)

        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account.status, test_status)
        self.assertEqual(scheme_account.display_status, scheme_account.JOIN)

    @patch('requests.get', auto_spec=True, return_value=MagicMock())
    def test_get_midas_balance_card_number_error(self, mock_request):
        test_status = SchemeAccount.CARD_NUMBER_ERROR
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        points = scheme_account.get_midas_balance(JourneyTypes.UPDATE)

        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account.status, test_status)
        self.assertEqual(scheme_account.display_status, scheme_account.WALLET_ONLY)

    @patch('requests.get', auto_spec=True, return_value=MagicMock())
    def test_get_midas_balance_general_error(self, mock_request):
        test_status = SchemeAccount.GENERAL_ERROR
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        points = scheme_account.get_midas_balance(JourneyTypes.UPDATE)

        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account.status, test_status)
        self.assertEqual(scheme_account.display_status, scheme_account.WALLET_ONLY)

    @patch('requests.get', auto_spec=True, return_value=MagicMock())
    def test_get_midas_join_error(self, mock_request):
        test_status = SchemeAccount.JOIN_ERROR
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        points = scheme_account.get_midas_balance(JourneyTypes.UPDATE)

        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account.status, test_status)
        self.assertEqual(scheme_account.display_status, scheme_account.WALLET_ONLY)

    @patch('requests.get', auto_spec=True, return_value=MagicMock())
    def test_get_midas_join_in_progress(self, mock_request):
        test_status = SchemeAccount.JOIN_IN_PROGRESS
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        points = scheme_account.get_midas_balance(JourneyTypes.UPDATE)

        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account.status, test_status)
        self.assertEqual(scheme_account.display_status, scheme_account.WALLET_ONLY)


class TestAccessTokens(APITestCase):
    @classmethod
    def setUpClass(cls):
        # Scheme Account 3
        cls.scheme_account_entry = SchemeAccountEntryFactory()
        cls.scheme_account = cls.scheme_account_entry.scheme_account
        question = SchemeCredentialQuestionFactory(type=CARD_NUMBER,
                                                   scheme=cls.scheme_account.scheme,
                                                   options=SchemeCredentialQuestion.LINK)
        cls.scheme = cls.scheme_account.scheme
        SchemeCredentialQuestionFactory(scheme=cls.scheme, type=USER_NAME, manual_question=True)

        cls.scheme_account_answer = SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account, question=question)
        cls.user = cls.scheme_account_entry.user

        # Scheme Account 2
        cls.scheme_account_entry2 = SchemeAccountEntryFactory()
        cls.scheme_account2 = cls.scheme_account_entry2.scheme_account
        question_2 = SchemeCredentialQuestionFactory(type=CARD_NUMBER, scheme=cls.scheme_account2.scheme)

        cls.second_scheme_account_answer = SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account2,
                                                                         question=question)
        cls.second_scheme_account_answer2 = SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account2,
                                                                          question=question_2)

        cls.scheme2 = cls.scheme_account2.scheme
        SchemeCredentialQuestionFactory(scheme=cls.scheme2, type=USER_NAME, manual_question=True)
        cls.scheme_account_answer2 = SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account2,
                                                                   question=cls.scheme2.manual_question)
        cls.user2 = cls.scheme_account_entry2.user

        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        cls.auth_service_headers = {'HTTP_AUTHORIZATION': 'Token ' + settings.SERVICE_API_KEY}
        super(TestAccessTokens, cls).setUpClass()

    @patch('analytics.api.update_attributes')
    @patch('analytics.api._get_today_datetime')
    def test_retrieve_scheme_accounts(self, mock_date, mock_update_attr):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)

        # GET Request
        response = self.client.get('/schemes/accounts/{}'.format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/schemes/accounts/{}'.format(self.scheme_account2.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)
        # DELETE Request
        response = self.client.delete('/schemes/accounts/{}'.format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            mock_update_attr.call_args[0][1],
            {
                '{0}'.format(self.scheme_account.scheme.company):
                    'true,ACTIVE,2000/05/19,{},prev_None,current_ACTIVE'.format(self.scheme_account.scheme.slug)
            }
        )

        response = self.client.delete('/schemes/accounts/{}'.format(self.scheme_account2.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)

        # Undo delete.
        self.scheme_account.is_deleted = False
        self.scheme_account.save()

    @patch.object(SchemeAccount, 'get_midas_balance')
    @patch('analytics.api._send_to_mnemosyne')
    def test_link_credentials(self, mock_send_to_mnemosyne, mock_get_midas_balance):
        mock_get_midas_balance.return_value = {
            'value': '10',
            'points': '100',
            'points_label': '100',
            'value_label': "$10",
            'reward_tier': 0,
            'balance': '20',
            'is_stale': False
        }
        data = {CARD_NUMBER: "London", 'consents': []}
        # Test Post Method
        response = self.client.post('/schemes/accounts/{0}/link'.format(self.scheme_account.id),
                                    data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 201)
        response = self.client.post('/schemes/accounts/{0}/link'.format(self.scheme_account2.id),
                                    data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 404)
        # Test Put Method
        response = self.client.put('/schemes/accounts/{0}/link'.format(self.scheme_account.id),
                                   data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        response = self.client.put('/schemes/accounts/{0}/link'.format(self.scheme_account2.id),
                                   data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 404)

    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_get_scheme_accounts_credentials(self, mock_get_midas_balance):
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'value_label': "$10",
            'reward_tier': 0,
            'balance': Decimal('20'),
            'is_stale': False
        }
        # Test with service headers
        response = self.client.get('/schemes/accounts/{0}/credentials'.format(self.scheme_account.id),
                                   **self.auth_service_headers)
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/schemes/accounts/{0}/credentials'.format(self.scheme_account2.id),
                                   **self.auth_service_headers)
        self.assertEqual(response.status_code, 200)
        # Test as standard user
        response = self.client.get('/schemes/accounts/{0}/credentials'.format(self.scheme_account.id),
                                   **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/schemes/accounts/{0}/credentials'.format(self.scheme_account2.id),
                                   **self.auth_headers)
        self.assertEqual(response.status_code, 404)

    def test_update_or_create_primary_credentials_barcode_to_card_number(self):
        scheme = SchemeFactory(card_number_regex='^([0-9]{19})([0-9]{5})$')
        SchemeCredentialQuestionFactory(type=CARD_NUMBER,
                                        scheme=scheme,
                                        options=SchemeCredentialQuestion.JOIN,
                                        manual_question=True)

        SchemeCredentialQuestionFactory(type=BARCODE,
                                        scheme=scheme,
                                        options=SchemeCredentialQuestion.JOIN,
                                        scan_question=True)

        self.scheme_account.scheme = scheme

        credentials = {'barcode': '633204003025524460012345'}
        new_credentials = self.scheme_account.update_or_create_primary_credentials(credentials)
        self.assertEqual(new_credentials, {'barcode': '633204003025524460012345',
                                           'card_number': '6332040030255244600'})

    def test_update_or_create_primary_credentials_card_number_to_barcode(self):
        scheme = SchemeFactory(barcode_regex='^([0-9]{19})([0-9]{5})$')
        SchemeCredentialQuestionFactory(type=CARD_NUMBER,
                                        scheme=scheme,
                                        options=SchemeCredentialQuestion.JOIN,
                                        manual_question=True)

        SchemeCredentialQuestionFactory(type=BARCODE,
                                        scheme=scheme,
                                        options=SchemeCredentialQuestion.JOIN,
                                        scan_question=True)

        self.scheme_account.scheme = scheme

        credentials = {'card_number': '633204003025524460012345'}
        new_credentials = self.scheme_account.update_or_create_primary_credentials(credentials)
        self.assertEqual(new_credentials, {'card_number': '633204003025524460012345',
                                           'barcode': '6332040030255244600'})

    def test_update_or_create_primary_credentials_does_nothing_when_only_one_primary_cred_in_scheme(self):
        scheme = SchemeFactory(card_number_regex='^([0-9]{19})([0-9]{5})$')
        SchemeCredentialQuestionFactory(type=CARD_NUMBER,
                                        scheme=scheme,
                                        options=SchemeCredentialQuestion.JOIN,
                                        manual_question=True)

        self.scheme_account.scheme = scheme

        credentials = {'barcode': '633204003025524460012345'}
        new_credentials = self.scheme_account.update_or_create_primary_credentials(credentials)
        self.assertEqual(new_credentials, {'barcode': '633204003025524460012345'})

    def test_update_or_create_primary_credentials_saves_non_regex_manual_question(self):
        scheme = SchemeFactory(card_number_regex='^([0-9]{19})([0-9]{5})$')
        SchemeCredentialQuestionFactory(type=EMAIL,
                                        scheme=scheme,
                                        options=SchemeCredentialQuestion.JOIN,
                                        manual_question=True)

        self.scheme_account.scheme = scheme

        self.assertFalse(self.scheme_account.manual_answer)
        credentials = {'email': 'testemail@testbink.com'}
        new_credentials = self.scheme_account.update_or_create_primary_credentials(credentials)
        self.assertEqual(new_credentials, {'email': 'testemail@testbink.com'})
        self.assertEqual(self.scheme_account.manual_answer.answer, 'testemail@testbink.com')


class TestSchemeAccountImages(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheme_account_entry = SchemeAccountEntryFactory()
        cls.scheme_account = cls.scheme_account_entry.scheme_account
        cls.scheme_account_image = SchemeAccountImageFactory(image_type_code=2)
        cls.scheme_account_image.scheme_accounts.add(cls.scheme_account)

        cls.scheme_images = [
            SchemeImageFactory(image_type_code=1, scheme=cls.scheme_account.scheme),
            SchemeImageFactory(image_type_code=2, scheme=cls.scheme_account.scheme),
            SchemeImageFactory(image_type_code=3, scheme=cls.scheme_account.scheme),
        ]

        cls.user = cls.scheme_account_entry.user
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        super().setUpClass()

    def test_image_property(self):
        serializer = ListSchemeAccountSerializer()
        images = serializer.get_images(self.scheme_account)
        our_image = next((i for i in images if i['image'] == self.scheme_account_image.image.url), None)
        self.assertIsNotNone(our_image)

    def test_CSV_upload(self):
        csv_file = SimpleUploadedFile("file.csv", content=b'', content_type="text/csv")
        response = self.client.post('/schemes/csv_upload', {'scheme': self.scheme_account.scheme.name,
                                                            'emails': csv_file},
                                    **self.auth_headers)
        self.assertEqual(response.status_code, 200)

    def test_images_have_object_type_properties(self):
        serializer = ListSchemeAccountSerializer()
        images = serializer.get_images(self.scheme_account)

        self.assertEqual(images[0]['object_type'], 'scheme_account_image')
        self.assertEqual(images[1]['object_type'], 'scheme_image')
        self.assertEqual(images[2]['object_type'], 'scheme_image')


class TestExchange(APITestCase):
    def test_get_donor_schemes(self):
        host_scheme = self.create_scheme()
        donor_scheme_1 = self.create_scheme()
        donor_scheme_2 = self.create_scheme()

        user = UserFactory()

        self.create_scheme_account(host_scheme, user)
        self.create_scheme_account(donor_scheme_2, user)
        self.create_scheme_account(donor_scheme_1, user)

        ExchangeFactory(host_scheme=host_scheme, donor_scheme=donor_scheme_1)
        ExchangeFactory(host_scheme=host_scheme, donor_scheme=donor_scheme_2)

        auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + settings.SERVICE_API_KEY}

        resp = self.client.get('/schemes/accounts/donor_schemes/{}/{}'.format(host_scheme.id, user.id), **auth_headers)
        self.assertEqual(resp.status_code, 200)

        json = resp.json()
        self.assertEqual(type(json), list)
        self.assertIn('donor_scheme', json[0])
        self.assertIn('exchange_rate_donor', json[0])
        self.assertIn('exchange_rate_host', json[0])
        self.assertIn('host_scheme', json[0])
        self.assertIn('info_url', json[0])
        self.assertIn('tip_in_url', json[0])
        self.assertIn('transfer_max', json[0])
        self.assertIn('transfer_min', json[0])
        self.assertIn('transfer_multiple', json[0])
        self.assertIn('scheme_account_id', json[0])
        self.assertIn('name', json[0]['donor_scheme'])
        self.assertIn('point_name', json[0]['donor_scheme'])
        self.assertIn('name', json[0]['host_scheme'])
        self.assertIn('point_name', json[0]['host_scheme'])

    @staticmethod
    def create_scheme_account(host_scheme, user):
        scheme_account = SchemeAccountFactory(scheme=host_scheme)
        SchemeCredentialAnswerFactory(scheme_account=scheme_account)
        SchemeAccountEntryFactory(user=user, scheme_account=scheme_account)
        return scheme_account

    @staticmethod
    def create_scheme():
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(type=CARD_NUMBER,
                                        scheme=scheme,
                                        scan_question=True,
                                        options=SchemeCredentialQuestion.LINK)
        return scheme


class TestSchemeAccountCredentials(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=cls.scheme, type=USER_NAME, manual_question=True)
        secondary_question = SchemeCredentialQuestionFactory(scheme=cls.scheme,
                                                             type=CARD_NUMBER,
                                                             options=SchemeCredentialQuestion.LINK)
        password_question = SchemeCredentialQuestionFactory(scheme=cls.scheme,
                                                            type=PASSWORD,
                                                            options=SchemeCredentialQuestion.LINK_AND_JOIN)

        cls.scheme_account = SchemeAccountFactory(scheme=cls.scheme)
        cls.scheme_account_answer = SchemeCredentialAnswerFactory(question=cls.scheme.manual_question,
                                                                  scheme_account=cls.scheme_account)
        SchemeCredentialAnswerFactory(question=secondary_question,
                                      scheme_account=cls.scheme_account)
        SchemeCredentialAnswerFactory(answer="testpassword",
                                      question=password_question,
                                      scheme_account=cls.scheme_account)

        cls.scheme_account2 = SchemeAccountFactory(scheme=cls.scheme)
        SchemeCredentialAnswerFactory(answer="testpassword",
                                      question=password_question,
                                      scheme_account=cls.scheme_account2)

        cls.scheme_account_no_answers = SchemeAccountFactory(scheme=cls.scheme)

        cls.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=cls.scheme_account)
        cls.scheme_account_entry2 = SchemeAccountEntryFactory(scheme_account=cls.scheme_account2)
        cls.scheme_account_entry_no_answers = SchemeAccountEntryFactory(scheme_account=cls.scheme_account_no_answers)

        cls.user = cls.scheme_account_entry.user
        cls.user2 = cls.scheme_account_entry2.user
        cls.user3 = cls.scheme_account_entry_no_answers.user
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        cls.auth_headers2 = {'HTTP_AUTHORIZATION': 'Token ' + cls.user2.create_token()}
        cls.auth_headers3 = {'HTTP_AUTHORIZATION': 'Token ' + cls.user3.create_token()}

        super().setUpClass()

    def send_delete_credential_request(self, data):
        response = self.client.delete('/schemes/accounts/{0}/credentials'.format(self.scheme_account.id),
                                      data=data, **self.auth_headers)
        return response

    def test_update_new_and_existing_credentials(self):
        response = self.client.put('/schemes/accounts/{0}/credentials'.format(self.scheme_account2.id),
                                   data={'card_number': '0123456', 'password': 'newpassword'}, **self.auth_headers2)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['updated'], ['card_number', 'password'])

        credential_list = self.scheme_account2.schemeaccountcredentialanswer_set.all()
        scheme_account_types = [answer.question.type for answer in credential_list]
        self.assertEqual(['card_number', 'password'], scheme_account_types)
        self.assertEqual(self.scheme_account2._collect_credentials()['password'], 'newpassword')

    def test_update_credentials_wrong_credential_type(self):
        response = self.client.put('/schemes/accounts/{0}/credentials'.format(self.scheme_account_no_answers.id),
                                   data={'title': 'mr'}, **self.auth_headers3)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['non_field_errors'][0], 'field(s) not found for scheme: title')
        credential_list = self.scheme_account_no_answers.schemeaccountcredentialanswer_set.all()
        self.assertEqual(len(credential_list), 0)

    def test_update_credentials_bad_credential_type(self):
        response = self.client.put('/schemes/accounts/{0}/credentials'.format(self.scheme_account_no_answers.id),
                                   data={'user_name': 'user_name not username'}, **self.auth_headers3)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['non_field_errors'][0], 'field(s) not found for scheme: user_name')
        credential_list = self.scheme_account_no_answers.schemeaccountcredentialanswer_set.all()
        self.assertEqual(len(credential_list), 0)

    def test_update_credentials_bad_credential_value_type_is_converted(self):
        response = self.client.put('/schemes/accounts/{0}/credentials'.format(self.scheme_account_no_answers.id),
                                   data={'card_number': True}, **self.auth_headers3)

        self.assertEqual(response.status_code, 200)

        credential_list = self.scheme_account_no_answers.schemeaccountcredentialanswer_set.all()
        scheme_account_types = [answer.question.type for answer in credential_list]
        self.assertEqual(['card_number'], scheme_account_types)
        self.assertEqual(self.scheme_account_no_answers._collect_credentials()['card_number'], 'True')

    def test_delete_credentials_by_type(self):
        response = self.send_delete_credential_request({'type_list': ['card_number', 'username']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['deleted'], "['card_number', 'username']")

        credential_list = self.scheme_account.schemeaccountcredentialanswer_set.all()
        scheme_account_types = [answer.question.type for answer in credential_list]
        self.assertTrue('card_number' not in scheme_account_types)

    def test_delete_credentials_by_property(self):
        response = self.send_delete_credential_request({'property_list': ['link_questions']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['deleted'], "['card_number', 'password']")

        credential_list = self.scheme_account.schemeaccountcredentialanswer_set.all()
        scheme_account_types = [answer.question.type for answer in credential_list]
        self.assertTrue('card_number' not in scheme_account_types)
        self.assertTrue('password' not in scheme_account_types)

    def test_delete_all_credentials(self):
        credential_list = self.scheme_account.schemeaccountcredentialanswer_set.all()
        self.assertEqual(len(credential_list), 3)
        response = self.send_delete_credential_request({'all': True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['deleted'], "['card_number', 'password', 'username']")

        new_credential_list = self.scheme_account.schemeaccountcredentialanswer_set.all()
        self.assertEqual(len(new_credential_list), 0)

    def test_delete_credentials_invalid_request(self):
        response = self.send_delete_credential_request({'all': 'not a boolean'})
        self.assertEqual(response.status_code, 400)
        self.assertTrue('is not a valid boolean' in str(response.json()))

        credential_list = self.scheme_account.schemeaccountcredentialanswer_set.all()
        self.assertEqual(len(credential_list), 3)

    def test_delete_credentials_wrong_credential(self):
        response = self.client.delete('/schemes/accounts/{0}/credentials'.format(self.scheme_account2.id),
                                      data={'type_list': ['card_number', 'password']}, **self.auth_headers2)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(response.json()['message'].startswith('No answers found for: card_number'))

        credential_list = self.scheme_account.schemeaccountcredentialanswer_set.all()
        self.assertEqual(len(credential_list), 3)

    def test_delete_credentials_with_scheme_account_without_credentials(self):
        response = self.client.delete('/schemes/accounts/{0}/credentials'.format(self.scheme_account_no_answers.id),
                                      data={'all': True}, **self.auth_headers3)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(response.json()['message'].startswith('No answers found'))

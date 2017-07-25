import datetime
import json


from decimal import Decimal
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from scheme.encyption import AESCipher
from rest_framework.test import APITestCase
from scheme.serializers import ResponseLinkSerializer, LinkSchemeSerializer, ListSchemeAccountSerializer
from scheme.tests.factories import SchemeFactory, SchemeCredentialQuestionFactory, SchemeCredentialAnswerFactory, \
    SchemeAccountFactory, SchemeAccountImageFactory, SchemeImageFactory, ExchangeFactory
from scheme.models import SchemeAccount
from scheme.views import CreateMy365AccountsAndLink
from user.models import Setting
from user.tests.factories import SettingFactory, UserSettingFactory
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from unittest.mock import patch, MagicMock
from scheme.credentials import PASSWORD, CARD_NUMBER, USER_NAME, CREDENTIAL_TYPES, BARCODE, EMAIL

from user.tests.factories import UserFactory


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
                                                             third_party_identifier=True)
        password_question = SchemeCredentialQuestionFactory(scheme=cls.scheme, type=PASSWORD)

        cls.scheme_account = SchemeAccountFactory(scheme=cls.scheme)
        cls.scheme_account_answer = SchemeCredentialAnswerFactory(question=cls.scheme.manual_question,
                                                                  scheme_account=cls.scheme_account)
        cls.second_scheme_account_answer = SchemeCredentialAnswerFactory(question=secondary_question,
                                                                         scheme_account=cls.scheme_account)

        cls.scheme_account_answer_password = SchemeCredentialAnswerFactory(answer="test_password",
                                                                           question=password_question,
                                                                           scheme_account=cls.scheme_account)
        cls.scheme1 = SchemeFactory(card_number_regex=r'(^[0-9]{16})', card_number_prefix='')
        cls.scheme_account1 = SchemeAccountFactory(scheme=cls.scheme1)
        barcode_question = SchemeCredentialQuestionFactory(scheme=cls.scheme1, type=BARCODE)
        SchemeCredentialQuestionFactory(scheme=cls.scheme1, type=CARD_NUMBER, third_party_identifier=True)
        cls.scheme_account_answer_barcode = SchemeCredentialAnswerFactory(answer="9999888877776666",
                                                                          question=barcode_question,
                                                                          scheme_account=cls.scheme_account1)
        cls.user = cls.scheme_account.user

        cls.scheme.save()
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        cls.auth_service_headers = {'HTTP_AUTHORIZATION': 'Token ' + settings.SERVICE_API_KEY}

        cls.scheme_account_image = SchemeAccountImageFactory()

        super().setUpClass()

    def test_scheme_account_query(self):
        resp = self.client.get('/schemes/accounts/query?scheme__slug={}&user__id={}'.format(self.scheme.slug,
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

    def test_join_account(self):
        join_scheme = SchemeFactory()
        question = SchemeCredentialQuestionFactory(scheme=join_scheme, type=USER_NAME, scan_question=True)
        join_account = SchemeAccountFactory(scheme=join_scheme, user=self.user, status=SchemeAccount.JOIN)

        response = self.client.post('/schemes/accounts', data={
            'scheme': join_scheme.id,
            'order': 0,
            question: 'test',
        }, **self.auth_headers)

        self.assertEqual(response.status_code, 201)

        data = response.json()
        print(data)
        self.assertEqual(data['id'], join_account.id)
        self.assertEqual(data['order'], 0)
        self.assertEqual(data['scheme'], join_scheme.id)
        self.assertEqual(data['username'], 'test')

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
        self.assertEqual(response.data['action_status'], 'ACTIVE')

    @patch('intercom.intercom_api.update_user_custom_attribute')
    @patch('intercom.intercom_api._get_today_datetime')
    def test_delete_sctest_delete_schemes_accountshemes_accounts(self, mock_date, mock_update_custom_attr):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        response = self.client.delete('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(
            mock_update_custom_attr.call_args[0][3],
            "true,ACTIVE,2000/05/19,{}".format(self.scheme_account.scheme.slug)
        )

        deleted_scheme_account = SchemeAccount.all_objects.get(id=self.scheme_account.id)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(deleted_scheme_account.is_deleted)

        response = self.client.get('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)
        response = self.client.post('/schemes/accounts/{0}/link'.format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)

    @patch('intercom.intercom_api.update_user_custom_attribute')
    @patch('intercom.intercom_api._get_today_datetime')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_link_schemes_account(self, mock_get_midas_balance, mock_date, mock_update_custom_attr):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'balance': Decimal('20'),
            'is_stale': False
        }
        data = {CARD_NUMBER: "London", PASSWORD: "sdfsdf"}
        response = self.client.post('/schemes/accounts/{0}/link'.format(self.scheme_account.id),
                                    data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['balance']['points'], '100.00')
        self.assertEqual(response.data['status_name'], "Active")
        self.assertTrue(ResponseLinkSerializer(data=response.data).is_valid())

        self.assertEqual(len(mock_update_custom_attr.call_args[0]), 4)

        self.assertEqual(
            mock_update_custom_attr.call_args[0][3],
            "false,ACTIVE,2000/05/19,{}".format(self.scheme_account.scheme.slug)
        )

    @patch('intercom.intercom_api.update_user_custom_attribute')
    @patch('intercom.intercom_api._get_today_datetime')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_put_link_schemes_account(self, mock_get_midas_balance, mock_date, mock_update_custom_attr):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'balance': Decimal('20'),
            'is_stale': False
        }
        manual_question_type = self.scheme_account.scheme.manual_question.type
        data = {manual_question_type: "Scotland"}
        response = self.client.put('/schemes/accounts/{0}/link'.format(self.scheme_account.id),
                                   data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['balance']['points'], '100.00')
        self.assertEqual(response.data['status_name'], "Active")
        self.assertEqual(response.data[manual_question_type], "Scotland")
        self.assertTrue(ResponseLinkSerializer(data=response.data).is_valid())

        self.assertEqual(len(mock_update_custom_attr.call_args[0]), 4)
        self.assertEqual(
            mock_update_custom_attr.call_args[0][3],
            "false,ACTIVE,2000/05/19,{}".format(self.scheme_account.scheme.slug)
        )

    def test_list_schemes_accounts(self):
        response = self.client.get('/schemes/accounts', **self.auth_headers)
        self.assertEqual(type(response.data), ReturnList)
        self.assertEqual(response.data[0]['scheme']['name'], self.scheme.name)
        self.assertEqual(response.data[0]['status_name'], 'Active')
        self.assertIn('barcode', response.data[0])
        self.assertIn('card_label', response.data[0])
        self.assertNotIn('barcode_regex', response.data[0]['scheme'])

    @patch('intercom.intercom_api.update_user_custom_attribute')
    @patch('intercom.intercom_api._get_today_datetime')
    def test_wallet_only(self, mock_date, mock_update_custom_attr):
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
            mock_update_custom_attr.call_args[0][3],
            "false,WALLET_ONLY,2000/05/19,{}".format(scheme.slug)
        )

    def test_scheme_account_update_status(self):
        data = {
            'status': 9
        }
        response = self.client.post('/schemes/accounts/{}/status/'.format(self.scheme_account.id), data=data,
                                    **self.auth_service_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.scheme_account.id)
        self.assertEqual(response.data['status'], 9)

    def test_scheme_account_update_status_bad(self):
        response = self.client.post('/schemes/accounts/{}/status/'.format(self.scheme_account.id),
                                    data={'status': 112},
                                    **self.auth_service_headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, ['Invalid status code sent.'])

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
        self.assertIn('action_status', response.data)
        self.assertIn('status_name', response.data)
        self.assertIn('user', response.data)
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

    def test_scheme_account_third_party_identifier(self):
        self.assertEqual(self.scheme_account.third_party_identifier, self.second_scheme_account_answer.answer)
        self.assertEqual(self.scheme_account1.third_party_identifier, self.scheme_account_answer_barcode.answer)

    def test_scheme_account_encrypted_credentials(self):
        decrypted_credentials = json.loads(AESCipher(settings.AES_KEY.encode()).decrypt(
            self.scheme_account.credentials()))

        self.assertEqual(decrypted_credentials, {'card_number': self.second_scheme_account_answer.answer,
                                                 'password': 'test_password',
                                                 'username': self.scheme_account_answer.answer})

    def test_scheme_account_encrypted_credentials_bad(self):
        scheme_account = SchemeAccountFactory(scheme=self.scheme, user=self.user)
        encrypted_credentials = scheme_account.credentials()
        self.assertIsNone(encrypted_credentials)
        self.assertEqual(scheme_account.status, SchemeAccount.INCOMPLETE)

    def test_scheme_account_answer_serializer(self):
        """
        If this test breaks you need to add the new credential to the SchemeAccountAnswerSerializer
        """
        self.assertEqual(set(dict(CREDENTIAL_TYPES).keys()), set(LinkSchemeSerializer._declared_fields.keys()))

    def test_unique_scheme_account(self):
        response = self.client.post('/schemes/accounts', data={'scheme': self.scheme_account.scheme.id,
                                                               USER_NAME: 'sdf', 'order': 0}, **self.auth_headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data,
                         {'non_field_errors': ["You already have an account for this scheme: '{}'".format(
                             str(self.scheme_account.scheme))]})

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

    @patch.object(CreateMy365AccountsAndLink, 'get_my360_schemes', return_value=['food_cellar_slug', 'deep_blue_slug'])
    @patch.object(SchemeAccount, '_get_balance')
    def test_my360_manual_create_account_view(self, mock_get_midas_balance, mock_get_schemes):
        # Given:
        # ['food_cellar_slug', 'deep_blue_slug'] schemes exist in 'Bink system'
        # ['food_cellar_slug', 'deep_blue_slug'] schemes accounts exist in 'My360 system'
        # ['food_cellar_slug', 'deep_blue_slug'] schemes accounts do not exist in 'Bink system'
        # a card_number scheme credential question with one_question_link is created for the each schema
        response_mock = MagicMock()
        response_mock.json = MagicMock(return_value={
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'balance': Decimal('20'),
            'is_stale': False
        })
        response_mock.status_code = 200
        mock_get_midas_balance.return_value = response_mock

        scheme_0 = SchemeFactory(slug='food_cellar_slug', id=999)
        scheme_1 = SchemeFactory(slug='deep_blue_slug', id=998)
        SchemeCredentialQuestionFactory(scheme=scheme_0, type=CARD_NUMBER, one_question_link=True)
        SchemeCredentialQuestionFactory(scheme=scheme_1, type=CARD_NUMBER, manual_question=True, one_question_link=True)

        # When the front end requests [POST] /schemes/accounts/my360
        data = {
            CARD_NUMBER: '123456789',
            'scheme': scheme_0.id,
            'order': 1
        }
        response = self.client.post('/schemes/accounts/my360', **self.auth_headers, data=data)

        # Then two schemes accounts are created in Bink
        self.assertEqual(response.status_code, 201)

        scheme_accounts = response.json()
        self.assertEqual(len(scheme_accounts), 2)

        self.assertEqual(scheme_accounts[0]['card_number'], '123456789')
        self.assertEqual(scheme_accounts[1]['card_number'], '123456789')

        self.assertEqual(scheme_accounts[0]['order'], 1)
        self.assertEqual(scheme_accounts[1]['order'], 1)

        self.assertIn('id', scheme_accounts[0])
        self.assertIn('id', scheme_accounts[1])

        self.assertIn('scheme', scheme_accounts[0])
        self.assertIn('scheme', scheme_accounts[1])

        self.assertEqual(scheme_accounts[0]['balance']['points'], '100.00')
        self.assertEqual(scheme_accounts[1]['balance']['points'], '100.00')

        self.assertEqual(scheme_accounts[0]['status_name'], "Active")
        self.assertEqual(scheme_accounts[1]['status_name'], "Active")

    @patch.object(CreateMy365AccountsAndLink, 'get_my360_schemes', return_value=[])
    @patch.object(SchemeAccount, '_get_balance')
    def test_my360_scan_create_account_no_schemes_associated(self, mock_get_midas_balance, mock_get_schemes):
        scheme_0 = SchemeFactory(slug='food_cellar_slug', id=999)
        SchemeCredentialQuestionFactory(scheme=scheme_0, type=BARCODE, scan_question=True, one_question_link=True)

        data = {
            BARCODE: '123456789',
            'scheme': scheme_0.id,
            'order': 1
        }
        response = self.client.post('/schemes/accounts/my360', **self.auth_headers, data=data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), [])

    @patch.object(CreateMy365AccountsAndLink, 'get_my360_schemes', return_value=['food_cellar_slug'])
    @patch.object(SchemeAccount, '_get_balance')
    def test_my360_manual_create_account_already_created(self, mock_get_midas_balance, mock_get_schemes):
        # Given:
        # food_cellar_slug scheme exists in 'Bink system'
        # a barcode scheme credential question are created for the schema
        # food_cellar_slug scheme account exists in 'My360 System'
        # food_cellar_slug scheme account exists in 'Bink System'
        scheme_0 = SchemeFactory(slug='food_cellar_slug', id=999)
        SchemeCredentialQuestionFactory(scheme=scheme_0, type=CARD_NUMBER, manual_question=True, one_question_link=True)

        scheme_account = SchemeAccountFactory(scheme=scheme_0, user=self.user)
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=PASSWORD)

        data = {
            CARD_NUMBER: '123456789',
            'scheme': scheme_0.id,
            'order': 1
        }
        response = self.client.post('/schemes/accounts/my360', **self.auth_headers, data=data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {
                'non_field_errors': [
                    "You already have an account for this scheme: '{}'".format(str(scheme_account.scheme))
                ]
            }
        )

    @patch.object(CreateMy365AccountsAndLink, 'get_my360_schemes', return_value=['food_cellar_slug'])
    @patch.object(SchemeAccount, '_get_balance')
    def test_my360_scan_create_account_already_created(self, mock_get_midas_balance, mock_get_schemes):
        # Given:
        # food_cellar_slug scheme exists in 'Bink system'
        # a barcode scheme credential question are created for the schema
        # And food_cellar_slug scheme account exists in 'My360 System'
        # And food_cellar_slug scheme account exists in 'Bink System'
        scheme_0 = SchemeFactory(slug='food_cellar_slug', id=999)
        SchemeCredentialQuestionFactory(scheme=scheme_0, type=BARCODE, scan_question=True, one_question_link=True)

        scheme_account = SchemeAccountFactory(scheme=scheme_0, user=self.user)
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=PASSWORD)

        data = {
            BARCODE: '123456789',
            'scheme': scheme_0.id,
            'order': 1
        }
        response = self.client.post('/schemes/accounts/my360', **self.auth_headers, data=data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {
                'non_field_errors': [
                    "You already have an account for this scheme: '{}'".format(str(scheme_account.scheme))
                ]
            }
        )

    @patch.object(CreateMy365AccountsAndLink, 'get_my360_schemes', return_value=['food_cellar_slug', 'deep_blue_slug'])
    @patch.object(SchemeAccount, '_get_balance')
    def test_my360_scan_create_account_view_food_cellar(self, mock_get_midas_balance, mock_get_schemes):
        # Given:
        # ['food_cellar_slug', 'deep_blue_slug'] schemes exist in 'Bink system'
        # a barcode scheme credential question is created for each schema
        # ['food_cellar_slug', 'deep_blue_slug'] scheme accounts do not exist in 'Bink System'
        # ['food_cellar_slug', 'deep_blue_slug'] scheme accounts exist in 'My360 System'
        response_mock = MagicMock()
        response_mock.json = MagicMock(return_value={
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'balance': Decimal('20'),
            'is_stale': False
        })
        response_mock.status_code = 200
        mock_get_midas_balance.return_value = response_mock

        scheme_0 = SchemeFactory(slug='food_cellar_slug', id=999)
        scheme_1 = SchemeFactory(slug='deep_blue_slug', id=998)

        SchemeCredentialQuestionFactory(scheme=scheme_0, type=BARCODE, scan_question=True, one_question_link=True)
        SchemeCredentialQuestionFactory(scheme=scheme_1, type=BARCODE, scan_question=True, one_question_link=True)

        # When the front end requests [POST] /schemes/accounts/my360
        data = {
            BARCODE: '123456789',
            'scheme': scheme_0.id,
            'order': 1
        }
        response = self.client.post('/schemes/accounts/my360', **self.auth_headers, data=data)
        self.assertEqual(response.status_code, 201)

        scheme_accounts = response.json()
        self.assertEqual(len(scheme_accounts), 2)

        self.assertEqual(scheme_accounts[0]['barcode'], '123456789')
        self.assertEqual(scheme_accounts[1]['barcode'], '123456789')

        self.assertEqual(scheme_accounts[0]['order'], 1)
        self.assertEqual(scheme_accounts[1]['order'], 1)

        self.assertIn('id', scheme_accounts[0])
        self.assertIn('id', scheme_accounts[1])

        self.assertIn('scheme', scheme_accounts[0])
        self.assertIn('scheme', scheme_accounts[1])

        self.assertEqual(scheme_accounts[0]['balance']['points'], '100.00')
        self.assertEqual(scheme_accounts[1]['balance']['points'], '100.00')

        self.assertEqual(scheme_accounts[0]['status_name'], "Active")
        self.assertEqual(scheme_accounts[1]['status_name'], "Active")

    @patch('intercom.intercom_api.post_issued_join_card_event')
    @patch('intercom.intercom_api.update_user_custom_attribute')
    @patch('intercom.intercom_api._get_today_datetime')
    def test_create_join_account_and_notify_intercom(self, mock_date, mock_update_custom_attr, mock_post_issued_event):
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
        self.assertIn('action_status', json)
        self.assertIn('barcode', json)
        self.assertIn('card_label', json)
        self.assertIn('created', json)
        self.assertIn('id', json)
        self.assertIn('images', json)
        self.assertIn('order', json)
        self.assertIn('scheme', json)
        self.assertIn('status', json)
        self.assertIn('user', json)

        self.assertEqual(mock_post_issued_event.call_count, 1)
        self.assertEqual(len(mock_post_issued_event.call_args[0]), 4)

        self.assertEqual(mock_update_custom_attr.call_count, 1)
        self.assertEqual(len(mock_update_custom_attr.call_args[0]), 4)
        self.assertEqual(mock_update_custom_attr.call_args[0][2], scheme.company)

        self.assertEqual(
            mock_update_custom_attr.call_args[0][3],
            "false,JOIN,2000/05/19,{}".format(scheme.slug)
        )

    @patch('intercom.intercom_api.post_issued_join_card_event')
    @patch('intercom.intercom_api.update_user_custom_attribute')
    def test_create_join_account_against_user_setting(self, mock_update_custom_attr, mock_post_issued_event):
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

        self.assertFalse(mock_post_issued_event.called)
        self.assertFalse(mock_update_custom_attr.called)


class TestSchemeAccountModel(APITestCase):
    def test_missing_credentials(self):
        scheme_account = SchemeAccountFactory()
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=PASSWORD)
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=CARD_NUMBER, scan_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=BARCODE, manual_question=True)
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
        scheme_account = SchemeAccountFactory()
        points = scheme_account.get_midas_balance()
        self.assertIsNone(points)
        self.assertTrue(mock_credentials.called)

    @patch('requests.get', auto_spec=True, return_value=MagicMock())
    def test_get_midas_balance(self, mock_request):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {'points': 500}
        scheme_account = SchemeAccountFactory()
        points = scheme_account.get_midas_balance()
        self.assertEqual(points['points'], 500)
        self.assertFalse(points['is_stale'])
        self.assertEqual(scheme_account.status, SchemeAccount.ACTIVE)

    @patch('requests.get', auto_spec=True, side_effect=ConnectionError)
    def test_get_midas_balance_connection_error(self, mock_request):
        scheme_account = SchemeAccountFactory()
        points = scheme_account.get_midas_balance()
        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account.status, SchemeAccount.MIDAS_UNREACHABLE)


class TestAccessTokens(APITestCase):
    @classmethod
    def setUpClass(cls):
        # Scheme Account 3
        cls.scheme_account = SchemeAccountFactory()
        question = SchemeCredentialQuestionFactory(type=CARD_NUMBER, scheme=cls.scheme_account.scheme)
        cls.scheme = cls.scheme_account.scheme
        SchemeCredentialQuestionFactory(scheme=cls.scheme, type=USER_NAME, manual_question=True)

        cls.scheme_account_answer = SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account, question=question)
        cls.user = cls.scheme_account.user

        # Scheme Account 2
        cls.scheme_account2 = SchemeAccountFactory()
        question_2 = SchemeCredentialQuestionFactory(type=CARD_NUMBER, scheme=cls.scheme_account2.scheme)

        cls.second_scheme_account_answer = SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account2,
                                                                         question=question)
        cls.second_scheme_account_answer2 = SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account2,
                                                                          question=question_2)

        cls.scheme2 = cls.scheme_account2.scheme
        SchemeCredentialQuestionFactory(scheme=cls.scheme2, type=USER_NAME, manual_question=True)
        cls.scheme_account_answer2 = SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account2,
                                                                   question=cls.scheme2.manual_question)
        cls.user2 = cls.scheme_account2.user

        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        cls.auth_service_headers = {'HTTP_AUTHORIZATION': 'Token ' + settings.SERVICE_API_KEY}
        super(TestAccessTokens, cls).setUpClass()

    @patch('intercom.intercom_api.update_user_custom_attribute')
    @patch('intercom.intercom_api._get_today_datetime')
    def test_retrieve_scheme_accounts(self, mock_date, mock_update_custom_attr):
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
            mock_update_custom_attr.call_args[0][3],
            "true,ACTIVE,2000/05/19,{}".format(self.scheme_account.scheme.slug)
        )

        response = self.client.delete('/schemes/accounts/{}'.format(self.scheme_account2.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)

        # Undo delete.
        self.scheme_account.is_deleted = False
        self.scheme_account.save()

    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_link_credentials(self, mock_get_midas_balance):
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'balance': Decimal('20'),
            'is_stale': False
        }
        data = {CARD_NUMBER: "London"}
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


class TestSchemeAccountImages(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheme_account = SchemeAccountFactory()
        cls.scheme_account_image = SchemeAccountImageFactory(image_type_code=2)
        cls.scheme_account_image.scheme_accounts.add(cls.scheme_account)

        cls.scheme_images = [
            SchemeImageFactory(image_type_code=1, scheme=cls.scheme_account.scheme),
            SchemeImageFactory(image_type_code=2, scheme=cls.scheme_account.scheme),
            SchemeImageFactory(image_type_code=3, scheme=cls.scheme_account.scheme),
        ]

        cls.user = cls.scheme_account.user
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
        scheme_account = SchemeAccountFactory(user=user, scheme=host_scheme)
        SchemeCredentialAnswerFactory(scheme_account=scheme_account)
        return scheme_account

    @staticmethod
    def create_scheme():
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(type=CARD_NUMBER, scheme=scheme, scan_question=True)
        return scheme

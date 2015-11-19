from decimal import Decimal
from django.conf import settings
from scheme.encyption import AESCipher
from rest_framework.test import APITestCase
from scheme.serializers import ResponseLinkSerializer, LinkSchemeSerializer
from scheme.tests.factories import SchemeFactory, SchemeCredentialQuestionFactory, SchemeCredentialAnswerFactory, \
    SchemeAccountFactory
from scheme.models import SchemeAccount
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from unittest.mock import patch
from django.test import SimpleTestCase
from scheme.credentials import PASSWORD, CARD_NUMBER, USER_NAME, CREDENTIAL_TYPES
import json


class TestSchemeAccount(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheme_account_answer = SchemeCredentialAnswerFactory(type=USER_NAME)
        cls.scheme_account = cls.scheme_account_answer.scheme_account
        cls.second_scheme_account_answer = SchemeCredentialAnswerFactory(type=CARD_NUMBER,
                                                                         scheme_account=cls.scheme_account)

        cls.scheme_account_answer_password = SchemeCredentialAnswerFactory(answer="test_password", type=PASSWORD,
                                                                           scheme_account=cls.scheme_account)

        cls.scheme = cls.scheme_account.scheme
        cls.user = cls.scheme_account.user
        cls.scheme.primary_question = SchemeCredentialQuestionFactory(scheme=cls.scheme, type=USER_NAME)
        cls.scheme.secondary_question = SchemeCredentialQuestionFactory(scheme=cls.scheme, type=CARD_NUMBER)

        cls.scheme.save()
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        cls.auth_service_headers = {'HTTP_AUTHORIZATION': 'Token ' + settings.SERVICE_API_KEY}
        super(TestSchemeAccount, cls).setUpClass()

    def test_get_scheme_account(self):
        response = self.client.get('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.scheme_account.id)
        self.assertEqual(response.data['primary_answer_id'], self.scheme_account_answer.id)
        self.assertEqual(len(response.data['answers']), 3)
        self.assertIn('answer', response.data['answers'][0])
        self.assertEqual(response.data['answers'][0]['answer'], '****')
        self.assertEqual(response.data['scheme']['id'], self.scheme.id)
        self.assertEqual(response.data['scheme']['is_barcode'], True)
        self.assertEqual(response.data['action_status'], 'ACTIVE')

    def test_put_schemes_account(self):
        new_scheme = SchemeFactory()
        data = {'order': 5, 'scheme': new_scheme.id, 'primary_answer': '234234234'}
        response = self.client.put('/schemes/accounts/{0}'.format(self.scheme_account.id), data=data,
                                   **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        primary_answer_id = response.data['primary_answer_id']
        self.assertEqual(response.data['order'], 5)
        for answer in response.data['answers']:
            if answer['id'] == primary_answer_id:
                self.assertEqual(answer['answer'], '234234234')

    def test_patch_schemes_account(self):
        response = self.client.put('/schemes/accounts/{}'.format(self.scheme_account.id), data={},
                                   **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        content = response.data
        self.assertEqual(content['order'], self.scheme_account.order)

    def test_delete_schemes_accounts(self):
        response = self.client.delete('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)
        deleted_scheme_account = SchemeAccount.objects.get(id=self.scheme_account.id)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(deleted_scheme_account.is_deleted)

        response = self.client.get('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)

    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_link_schemes_account(self, mock_get_midas_balance):
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'value_label': "$10",
            'balance': Decimal('20'),
            'is_stale': False
        }
        data = {CARD_NUMBER: "London"}
        response = self.client.post('/schemes/accounts/{0}/link'.format(self.scheme_account.id),
                                    data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['balance']['points'], '100.00')
        self.assertEqual(response.data['status_name'], "Active")
        self.assertTrue(ResponseLinkSerializer(data=response.data).is_valid())

    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_put_link_schemes_account(self, mock_get_midas_balance):
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'value_label': "$10",
            'balance': Decimal('20'),
            'is_stale': False
        }
        data = {"primary_answer": "Scotland"}
        primary_question_type = self.scheme_account.scheme.primary_question.type
        response = self.client.put('/schemes/accounts/{0}/link'.format(self.scheme_account.id),
                                   data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['balance']['points'], '100.00')
        self.assertEqual(response.data['status_name'], "Active")
        self.assertEqual(response.data[primary_question_type], "Scotland")
        self.assertTrue(ResponseLinkSerializer(data=response.data).is_valid())

    def test_list_schemes_accounts(self):
        response = self.client.get('/schemes/accounts', **self.auth_headers)
        self.assertEqual(type(response.data), ReturnList)
        self.assertEqual(response.data[0]['scheme']['name'], self.scheme.name)
        self.assertEqual(response.data[0]['status_name'], 'Active')
        self.assertIn('primary_answer', response.data[0])

    def test_wallet_only(self):
        scheme = SchemeFactory()
        scheme.primary_question = SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER)
        scheme.save()

        response = self.client.post('/schemes/accounts', data={'scheme': scheme.id, 'primary_answer': '1234'},
                                    **self.auth_headers)
        self.assertEqual(response.status_code, 201)
        content = response.data
        self.assertEqual(content['scheme'], scheme.id)
        self.assertEqual(content['order'], 0)
        self.assertEqual(content['primary_answer'], '1234')
        self.assertEqual(content['primary_answer_type'], 'card_number')
        self.assertIn('/schemes/accounts/', response._headers['location'][1])
        self.assertEqual(SchemeAccount.objects.get(pk=content['id']).status, SchemeAccount.WALLET_ONLY)

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
        response = self.client.post('/schemes/accounts/{}/status/'.format(self.scheme_account.id), data={'status': 112},
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
        scheme = SchemeAccountFactory(status=SchemeAccount.LOCKED_BY_ENDSITE)
        scheme_2 = SchemeAccountFactory(status=SchemeAccount.ACTIVE)
        response = self.client.get('/schemes/accounts/system_retry', **self.auth_service_headers)
        scheme_ids = [result['id'] for result in response.data['results']]

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['next'])
        self.assertIn(scheme.id, scheme_ids)
        self.assertNotIn(scheme_2.id, scheme_ids)

    def test_get_scheme_accounts_credentials(self):
        response = self.client.get('/schemes/accounts/{0}/service_credentials'.format(self.scheme_account.id),
                                   **self.auth_service_headers)

        self.assertEqual(response.status_code, 200)
        self.assertIn('credentials', response.data)
        self.assertIn('scheme', response.data)
        self.assertIn('user', response.data)
        self.assertIn('id', response.data)

    def test_scheme_account_collect_credentials(self):
        self.assertEqual(self.scheme_account._collect_credentials(), {
            'card_number': self.second_scheme_account_answer.answer, 'password': 'test_password',
            'username': self.scheme_account_answer.answer})

    def test_scheme_account_encrypted_credentials(self):
        decrypted_credentials = json.loads(AESCipher(settings.AES_KEY.encode()).decrypt(
            self.scheme_account.credentials()))

        self.assertEqual(decrypted_credentials, {'card_number': self.second_scheme_account_answer.answer,
                                                 'password': 'test_password',
                                                 'username': self.scheme_account_answer.answer})

    def test_scheme_account_encrypted_credentials_bad(self):
        scheme_account = SchemeAccount(scheme=self.scheme, user=self.user)
        encrypted_credentials = scheme_account.credentials()
        self.assertIsNone(encrypted_credentials)
        self.assertEqual(scheme_account.status, SchemeAccount.INCOMPLETE)

    def test_scheme_account_answer_serializer(self):
        """
        If this test breaks you need to add the new credential to the SchemeAccountAnswerSerializer
        """
        self.assertEqual(set(dict(CREDENTIAL_TYPES).keys()), set(LinkSchemeSerializer._declared_fields.keys()))

    def test_unique_scheme_account(self):
        response = self.client.post('/schemes/accounts', data={'scheme': self.scheme_account.id,
                                                               'primary_answer': '1234'}, **self.auth_headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data,
                         {'non_field_errors': ["You already have an account for this scheme: '{}'".format(
                             self.scheme_account.scheme.name)]})

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

    def test_valid_credentials(self):
        self.assertEqual(self.scheme_account.missing_credentials([]), set(['card_number', 'username']))
        self.assertFalse(self.scheme_account.missing_credentials(['card_number', 'username', 'dummy']))


class TestAnswerValidation(SimpleTestCase):
    def test_email_validation_error(self):
        serializer = LinkSchemeSerializer(data={"email": "bobgmail.com"})
        self.assertFalse(serializer.is_valid())

    def test_memorable_date_validation_error(self):
        serializer = LinkSchemeSerializer(data={"memorable_date": "122/11/2015"})
        self.assertFalse(serializer.is_valid())

    @patch.object(LinkSchemeSerializer, 'validate')
    def test_memorable_date_validation(self, mock_validate):
        serializer = LinkSchemeSerializer(data={"memorable_date": "22/11/2015"})
        self.assertTrue(serializer.is_valid())

    def test_pin_validation_error(self):
        serializer = LinkSchemeSerializer(data={"pin": "das33"})
        self.assertFalse(serializer.is_valid())

    @patch.object(LinkSchemeSerializer, 'validate')
    def test_pin_validation(self, mock_validate):
        serializer = LinkSchemeSerializer(data={"pin": "3333"})
        self.assertTrue(serializer.is_valid())

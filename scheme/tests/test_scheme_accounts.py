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
from scheme.credentials import PASSWORD, CARD_NUMBER, USER_NAME, CREDENTIAL_TYPES, BARCODE, EMAIL
import json


class TestSchemeAccountViews(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=cls.scheme, type=USER_NAME, manual_question=True)
        secondary_question = SchemeCredentialQuestionFactory(scheme=cls.scheme, type=CARD_NUMBER)
        password_question = SchemeCredentialQuestionFactory(scheme=cls.scheme, type=PASSWORD)

        cls.scheme_account = SchemeAccountFactory(scheme=cls.scheme)
        cls.scheme_account_answer = SchemeCredentialAnswerFactory(question=cls.scheme.manual_question,
                                                                  scheme_account=cls.scheme_account)
        cls.second_scheme_account_answer = SchemeCredentialAnswerFactory(question=secondary_question,
                                                                         scheme_account=cls.scheme_account)

        cls.scheme_account_answer_password = SchemeCredentialAnswerFactory(answer="test_password",
                                                                           question=password_question,
                                                                           scheme_account=cls.scheme_account)
        cls.user = cls.scheme_account.user

        cls.scheme.save()
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        cls.auth_service_headers = {'HTTP_AUTHORIZATION': 'Token ' + settings.SERVICE_API_KEY}
        super().setUpClass()

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

    def test_delete_schemes_accounts(self):
        response = self.client.delete('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)
        deleted_scheme_account = SchemeAccount.all_objects.get(id=self.scheme_account.id)

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
        data = {CARD_NUMBER: "London", PASSWORD: "sdfsdf"}
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
        manual_question_type = self.scheme_account.scheme.manual_question.type
        data = {manual_question_type: "Scotland"}
        response = self.client.put('/schemes/accounts/{0}/link'.format(self.scheme_account.id),
                                   data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['balance']['points'], '100.00')
        self.assertEqual(response.data['status_name'], "Active")
        self.assertEqual(response.data[manual_question_type], "Scotland")
        self.assertTrue(ResponseLinkSerializer(data=response.data).is_valid())

    def test_list_schemes_accounts(self):
        response = self.client.get('/schemes/accounts', **self.auth_headers)
        self.assertEqual(type(response.data), ReturnList)
        self.assertEqual(response.data[0]['scheme']['name'], self.scheme.name)
        self.assertEqual(response.data[0]['status_name'], 'Active')
        self.assertNotIn('barcode_regex', response.data[0]['scheme'])

    def test_wallet_only(self):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER, manual_question=True)

        response = self.client.post('/schemes/accounts', data={'scheme': scheme.id, CARD_NUMBER: '1234'},
                                    **self.auth_headers)
        self.assertEqual(response.status_code, 201)
        content = response.data
        self.assertEqual(content['scheme'], scheme.id)
        self.assertEqual(content['card_number'], '1234')
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
                                                               'manual_answer': '1234'}, **self.auth_headers)

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

    def test_retrieve_scheme_accounts(self):
        # GET Request
        response = self.client.get('/schemes/accounts/{}'.format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/schemes/accounts/{}'.format(self.scheme_account2.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)
        # DELETE Request
        response = self.client.delete('/schemes/accounts/{}'.format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 204)
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

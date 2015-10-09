from rest_framework.test import APITestCase
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from payment_card.tests import factories
from payment_card.models import PaymentCardAccount


class TestPaymentCard(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.payment_card_account = factories.PaymentCardAccountFactory()
        cls.payment_card = cls.payment_card_account.payment_card
        cls.user = cls.payment_card_account.user
        cls.issuer = cls.payment_card_account.issuer
        cls.auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + str(cls.user.uid),
        }
        super(TestPaymentCard, cls).setUpClass()

    def test_payment_card_list(self):
        response = self.client.get('/payment_cards/', **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnList)
        self.assertTrue(response.data)

    def test_get_payment_card_account(self):
        response = self.client.get('/payment_cards/accounts/{0}'.format(self.payment_card.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.payment_card.id)

    def test_post_payment_card_account(self):
        data = {'user': self.user.id,
                'security_code': '574',
                'issuer': self.issuer.id,
                'status': 0,
                'start_month': 8,
                'start_year': 2,
                'expiry_month': 4,
                'expiry_year': 10,
                'postcode': '28233',
                'payment_card': self.payment_card.id,
                'pan': '869978206660880',
                'name_on_card': 'Aron Stokes'}
        response = self.client.post('/payment_cards/accounts', data, **self.auth_headers)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertIn('id', response.data)

    def test_patch_payment_card_account(self):
        data = {'pan': '345345345'}
        response = self.client.patch('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                     data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['pan'], data['pan'])

    def test_delete_payment_card_accounts(self):
        response = self.client.delete('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                      **self.auth_headers)
        deleted_scheme_account = PaymentCardAccount.objects.get(id=self.payment_card_account.id)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(deleted_scheme_account.status, PaymentCardAccount.DELETED)
        response = self.client.get('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                   **self.auth_headers)
        self.assertEqual(response.status_code, 404)

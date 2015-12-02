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
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        super(TestPaymentCard, cls).setUpClass()

    def test_payment_card_list(self):
        response = self.client.get('/payment_cards', **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnList)
        self.assertTrue(response.data)

    def test_get_payment_card_account(self):
        response = self.client.get('/payment_cards/accounts/{0}'.format(self.payment_card.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.payment_card.id)
        self.assertNotIn('token', response.data)
        self.assertEqual(response.data['status_name'], 'pending')

    def test_post_payment_card_account(self):
        data = {'user': self.user.id,
                'issuer': self.issuer.id,
                'status': 1,
                'expiry_month': 4,
                'expiry_year': 10,
                'payment_card': self.payment_card.id,
                'pan_start': '9820',
                'pan_end': '088012',
                'country': 'New Zealand',
                'currency_code': 'GBP',
                'name_on_card': 'Aron Stokes',
                'token': "some-token"}
        response = self.client.post('/payment_cards/accounts', data, **self.auth_headers)
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('token', response.data)
        payment_card_account = PaymentCardAccount.objects.get(id=response.data['id'])
        self.assertEqual(payment_card_account.token, "some-token")
        self.assertEqual(payment_card_account.status, 0)

    def test_patch_payment_card_account(self):
        response = self.client.patch('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                     data={'pan_start': '987678'}, **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['pan_start'], "987678")

    def test_patch_payment_card_account_bad_length(self):
        response = self.client.patch('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                     data={'pan_start': '0000000'}, **self.auth_headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'pan_start': ['Ensure this field has no more than 6 characters.']})

        response = self.client.patch('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                     data={'pan_end': '0000000'}, **self.auth_headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'pan_end': ['Ensure this field has no more than 6 characters.']})

    def test_patch_payment_card_cannot_change_scheme(self):
        payment_card_2 = factories.PaymentCardFactory(name='sommet', slug='sommet')
        response = self.client.patch('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                     data={'payment_card': payment_card_2.id}, **self.auth_headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'payment_card': ['Cannot change payment card for payment card account.']})

    def test_put_payment_card_cannot_change_scheme(self):
        payment_card_2 = factories.PaymentCardFactory(name='sommet', slug='sommet')
        response = self.client.put('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                     data={'issuer': self.issuer.id,
                                           'pan_end': '000000',
                                           'payment_card': payment_card_2.id}, **self.auth_headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'payment_card': ['Cannot change payment card for payment card account.']})


    def test_delete_payment_card_accounts(self):
        response = self.client.delete('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                      **self.auth_headers)
        self.assertEqual(response.status_code, 204)
        response = self.client.get('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                   **self.auth_headers)
        self.assertEqual(response.status_code, 404)

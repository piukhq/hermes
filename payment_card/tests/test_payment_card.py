import arrow
import httpretty
from rest_framework.test import APITestCase
from payment_card.tests.factories import PaymentCardAccountFactory, PaymentCardAccountImageFactory, \
    PaymentCardImageFactory
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from payment_card.tests import factories
from payment_card.models import PaymentCardAccount, Image
from scheme.tests.factories import SchemeAccountFactory
from user.tests.factories import UserFactory
from django.conf import settings


class TestPaymentCardImages(APITestCase):

    @classmethod
    def setUpClass(cls):
        user = UserFactory()
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + user.create_token()}
        cls.image = PaymentCardImageFactory(status=Image.DRAFT,
                                            start_date=arrow.now().replace(hours=-1).datetime,
                                            end_date=arrow.now().replace(hours=1).datetime)

        super().setUpClass()

    def test_no_draft_images_in_payment_cards_list(self):
        resp = self.client.get('/payment_cards', **self.auth_headers)
        our_payment_card = [s for s in resp.json() if s['slug'] == self.image.payment_card.slug][0]
        self.assertEqual(0, len(our_payment_card['images']))

        self.image.status = Image.PUBLISHED
        self.image.save()

        resp = self.client.get('/payment_cards', **self.auth_headers)
        our_payment_card = [s for s in resp.json() if s['slug'] == self.image.payment_card.slug][0]
        self.assertEqual(1, len(our_payment_card['images']))


class TestPaymentCard(APITestCase):

    @classmethod
    def setUpClass(cls):
        cls.payment_card_account = factories.PaymentCardAccountFactory(psp_token='token')
        cls.payment_card = cls.payment_card_account.payment_card
        cls.user = cls.payment_card_account.user
        cls.issuer = cls.payment_card_account.issuer
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        cls.auth_service_headers = {'HTTP_AUTHORIZATION': 'Token ' + settings.SERVICE_API_KEY}

        cls.payment_card_image = PaymentCardAccountImageFactory()

        super(TestPaymentCard, cls).setUpClass()

    def test_payment_card_list(self):
        response = self.client.get('/payment_cards', **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnList)
        self.assertTrue(response.data)

    def test_list_payment_card_accounts(self):
        response = self.client.get('/payment_cards/accounts', **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), list)

        self.assertIn('currency_code', response.data[0])
        self.assertIn('status_name', response.data[0])
        self.assertNotIn('psp_token', response.data[0])
        self.assertNotIn('token', response.data[0])

    def test_get_payment_card_account(self):
        response = self.client.get(
            '/payment_cards/accounts/{0}'.format(self.payment_card_account.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.payment_card_account.id)
        self.assertNotIn('psp_token', response.data)
        self.assertNotIn('token', response.data)
        self.assertEqual(response.data['status_name'], 'pending')

    @httpretty.activate
    def test_post_payment_card_account(self):

        # Setup stub for HTTP request to METIS service within ListCreatePaymentCardAccount view.
        httpretty.register_uri(httpretty.POST, settings.METIS_URL + '/payment_service/payment_card', status=201)

        data = {'issuer': self.issuer.id,
                'status': 1,
                'expiry_month': 4,
                'expiry_year': 10,
                'payment_card': self.payment_card.id,
                'pan_start': '088012',
                'pan_end': '9820',
                'country': 'New Zealand',
                'currency_code': 'GBP',
                'name_on_card': 'Aron Stokes',
                'token': "some-token",
                'fingerprint': 'test-fingerprint',
                'order': 0}

        response = self.client.post('/payment_cards/accounts', data, **self.auth_headers)
        # The stub is called indirectly via the View so we can only verify the stub has been called
        self.assertTrue(httpretty.has_request())
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('psp_token', response.data)
        self.assertNotIn('token', response.data)
        payment_card_account = PaymentCardAccount.objects.get(id=response.data['id'])
        self.assertEqual(payment_card_account.psp_token, "some-token")
        self.assertEqual(payment_card_account.status, 0)
        self.assertEqual(payment_card_account.pan_end, '9820')

    @httpretty.activate
    def test_post_long_pan_end(self):
        # Setup stub for HTTP request to METIS service within ListCreatePaymentCardAccount view.
        httpretty.register_uri(httpretty.POST, settings.METIS_URL + '/payment_service/payment_card', status=201)

        data = {'issuer': self.issuer.id,
                'status': 1,
                'expiry_month': 4,
                'expiry_year': 10,
                'payment_card': self.payment_card.id,
                'pan_start': '088012',
                'pan_end': '49820',
                'country': 'New Zealand',
                'currency_code': 'GBP',
                'name_on_card': 'Aron Stokes',
                'token': "some-token",
                'fingerprint': 'test-fingerprint',
                'order': 0}

        response = self.client.post('/payment_cards/accounts', data, **self.auth_headers)

        # The stub is called indirectly via the View so we can only verify the stub has been called
        self.assertTrue(httpretty.has_request())
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('psp_token', response.data)
        self.assertNotIn('token', response.data)
        payment_card_account = PaymentCardAccount.objects.get(id=response.data['id'])
        self.assertEqual(payment_card_account.psp_token, "some-token")
        self.assertEqual(payment_card_account.status, 0)
        self.assertEqual(payment_card_account.pan_end, '9820')

    @httpretty.activate
    def test_post_barclays_payment_card_account(self):
        # add barclays offer image
        offer_image = PaymentCardAccountImageFactory(description='barclays', image_type_code=2)

        # add hero image
        hero_image = PaymentCardAccountImageFactory(
            description='barclays', image_type_code=0, payment_card=self.payment_card)

        # Setup stub for HTTP request to METIS service within ListCreatePaymentCardAccount view.
        httpretty.register_uri(httpretty.POST, settings.METIS_URL + '/payment_service/payment_card', status=201)

        data = {'issuer': self.issuer.id,
                'status': 1,
                'expiry_month': 4,
                'expiry_year': 10,
                'payment_card': self.payment_card.id,
                'pan_start': '543979',
                'pan_end': '9820',
                'country': 'New Zealand',
                'currency_code': 'GBP',
                'name_on_card': 'Aron Stokes',
                'token': 'some-token',
                'fingerprint': 'test-fingerprint',
                'order': 0}

        self.assertFalse(offer_image.payment_card_accounts.exists())
        self.assertFalse(hero_image.payment_card_accounts.exists())
        response = self.client.post('/payment_cards/accounts', data, **self.auth_headers)

        self.assertEqual(response.status_code, 201)
        payment_card_account = PaymentCardAccount.objects.get(id=response.data['id'])
        self.assertEqual(offer_image.payment_card_accounts.first(), payment_card_account)
        self.assertEqual(hero_image.payment_card_accounts.first(), payment_card_account)

    def test_patch_payment_card_account(self):
        response = self.client.patch('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                     data={'pan_start': '987678'}, **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['pan_start'], "987678")

    # def test_patch_payment_card_account_bad_length(self):
    #     response = self.client.patch('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
    #                                  data={'pan_start': '0000000'}, **self.auth_headers)
    #     self.assertEqual(response.status_code, 400)
    #     self.assertEqual(response.data, {'pan_start': ['Ensure this field has no more than 6 characters.']})

    #     response = self.client.patch('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
    #                                  data={'pan_end': '0000000'}, **self.auth_headers)
    #     self.assertEqual(response.status_code, 400)
    #     self.assertEqual(response.data, {'pan_end': ['Ensure this field has no more than 4 characters.']})

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
                                         'pan_end': '0000',
                                         'payment_card': payment_card_2.id}, **self.auth_headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'payment_card': ['Cannot change payment card for payment card account.']})

    def test_put_payment_card_account_status(self):
        response = self.client.put('/payment_cards/accounts/status',
                                   data={'status': 1, 'id': self.payment_card_account.id},
                                   **self.auth_service_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.payment_card_account.id)
        self.assertEqual(response.data['status'], 1)

    def test_put_invalid_payment_card_account_status(self):
        response = self.client.put('/payment_cards/accounts/status',
                                   data={'status': 9999, 'id': self.payment_card_account.id},
                                   **self.auth_service_headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data[0], 'Invalid status code sent.')

    def test_payment_card_account_token_unique(self):

        data = {'user': self.user.id,
                'issuer': self.issuer.id,
                'status': 1,
                'expiry_month': 4,
                'expiry_year': 10,
                'payment_card': self.payment_card.id,
                'pan_start': '088012',
                'pan_end': '9820',
                'country': 'New Zealand',
                'currency_code': 'GBP',
                'name_on_card': 'Aron Stokes',
                'token': self.payment_card_account.token,
                'fingerprint': 'test-fingerprint',
                'order': 0}
        response = self.client.post('/payment_cards/accounts', data, **self.auth_headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'token': ['This field must be unique.']})

    @httpretty.activate
    def test_delete_payment_card_accounts(self):

        # Setup stub for HTTP request to METIS service within ListCreatePaymentCardAccount view.
        httpretty.register_uri(httpretty.DELETE, settings.METIS_URL + '/payment_service/payment_card', status=204)

        response = self.client.delete('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                      **self.auth_headers)
        self.assertEqual(response.status_code, 204)
        response = self.client.get('/payment_cards/accounts/{0}'.format(self.payment_card_account.id),
                                   **self.auth_headers)
        self.assertEqual(response.status_code, 404)
        # The stub is called indirectly via the View so we can only verify the stub has been called
        self.assertTrue(httpretty.has_request())

    def test_cant_delete_other_payment_card_account(self):
        payment_card = factories.PaymentCardAccountFactory(payment_card=self.payment_card)

        response = self.client.delete('/payment_cards/accounts/{0}'.format(payment_card.id),
                                      **self.auth_headers)
        self.assertEqual(response.status_code, 404)

    def test_get_payment_card_scheme_accounts(self):
        token = 'test_token_123'
        user = UserFactory()
        SchemeAccountFactory(user=user)
        PaymentCardAccountFactory(user=user, psp_token=token, payment_card=self.payment_card)
        response = self.client.get('/payment_cards/scheme_accounts/{0}'.format(token), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(len(response.data[0]), 3)
        keys = list(response.data[0].keys())
        self.assertEqual(keys[0], 'scheme_id')
        self.assertEqual(keys[1], 'user_id')
        self.assertEqual(keys[2], 'scheme_account_id')

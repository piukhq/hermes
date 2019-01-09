from rest_framework.test import APITestCase
from rest_framework.utils.serializer_helpers import ReturnList

from payment_card.models import PaymentCardAccount
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory
from scheme.models import SchemeAccount
from user.models import ClientApplicationBundle


class TestOrder(APITestCase):
    def test_scheme_list(self):
        scheme_account_entry = SchemeAccountEntryFactory()
        user = scheme_account_entry.user
        scheme_account = scheme_account_entry.scheme_account
        payment_card_entry = PaymentCardAccountEntryFactory()
        payment_card_account = payment_card_entry.payment_card_account
        bundle, created = ClientApplicationBundle.objects.get_or_create(bundle_id='com.bink.wallet', client=user.client)
        bundle.schemes.add(scheme_account.scheme.id)
        # to do: bundle.issuers.add payment issue id required when issues filter is added

        data = [{
            "id": scheme_account.id,
            "order": 6,
            "type": "scheme"
        }, {
            "id": payment_card_account.id,
            "order": 20,
            "type": "payment_card"
        }]

        auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + user.create_token()}
        response = self.client.post('/order', data=data, format='json', **auth_headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(type(response.data), ReturnList)
        self.assertEqual(SchemeAccount.objects.get(id=scheme_account.id).order, 6)
        self.assertEqual(PaymentCardAccount.objects.get(id=payment_card_account.id).order, 20)

    def test_scheme_list_other_bundle(self):
        scheme_account_entry = SchemeAccountEntryFactory()
        user = scheme_account_entry.user
        scheme_account = scheme_account_entry.scheme_account
        payment_card_entry = PaymentCardAccountEntryFactory()
        payment_card_account = payment_card_entry.payment_card_account
        bundle_id = 'my_test_bundle'
        bundle, created = ClientApplicationBundle.objects.get_or_create(bundle_id=bundle_id, client=user.client)
        bundle.schemes.add(scheme_account.scheme.id)
        # to do: bundle.issuers.add payment issue id required when issues filter is added

        data = [{
            "id": scheme_account.id,
            "order": 6,
            "type": "scheme"
        }, {
            "id": payment_card_account.id,
            "order": 20,
            "type": "payment_card"
        }]

        auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + user.create_token(bundle_id)}
        response = self.client.post('/order', data=data, format='json', **auth_headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(type(response.data), ReturnList)
        self.assertEqual(SchemeAccount.objects.get(id=scheme_account.id).order, 6)
        self.assertEqual(PaymentCardAccount.objects.get(id=payment_card_account.id).order, 20)

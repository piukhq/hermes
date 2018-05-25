from rest_framework.test import APITestCase
from rest_framework.utils.serializer_helpers import ReturnList
from scheme.tests.factories import SchemeAccountFactory
from payment_card.tests.factories import PaymentCardAccountFactory
from scheme.models import SchemeAccount
from payment_card.models import PaymentCardAccount


class TestOrder(APITestCase):
    def test_scheme_list(self):
        scheme_account = SchemeAccountFactory()
        payment_card_account = PaymentCardAccountFactory()
        data = [{
            "id": scheme_account.id,
            "order": 6,
            "type": "scheme"
        }, {
            "id": payment_card_account.id,
            "order": 20,
            "type": "payment_card"
        }]
        auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + scheme_account.prop.create_token()}
        response = self.client.post('/order', data=data, format='json', **auth_headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(type(response.data), ReturnList)
        self.assertEqual(SchemeAccount.objects.get(id=scheme_account.id).order, 6)
        self.assertEqual(PaymentCardAccount.objects.get(id=payment_card_account.id).order, 20)

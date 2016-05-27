import json
from rest_framework.test import APITestCase
from hermes import settings
from payment_card.tests import factories as payment_card_factories
from scheme.tests import factories as scheme_factories
from user.tests import factories as user_factories


class TestRetrieveLoyaltyID(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.user_1 = user_factories.UserFactory()
        cls.user_2 = user_factories.UserFactory()

        cls.payment_card_account_1 = payment_card_factories.PaymentCardAccountFactory(user=cls.user_1,
                                                                                      token='1122**33')
        cls.payment_card_account_2 = payment_card_factories.PaymentCardAccountFactory(user=cls.user_2,
                                                                                      token='3322**11')

        cls.scheme_account_1 = scheme_factories.SchemeAccountFactory(user=cls.user_1)
        cls.scheme = cls.scheme_account_1.scheme
        cls.scheme_account_2 = scheme_factories.SchemeAccountFactory(scheme=cls.scheme, user=cls.user_2)

        cls.scheme_question = scheme_factories.SchemeCredentialQuestionFactory(scheme=cls.scheme,
                                                                               third_party_identifier=True)

        cls.scheme_answer_1 = scheme_factories.SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account_1,
                                                                             question=cls.scheme_question)
        cls.scheme_answer_2 = scheme_factories.SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account_2,
                                                                             question=cls.scheme_question)

        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + settings.SERVICE_API_KEY}
        super(TestRetrieveLoyaltyID, cls).setUpClass()

    def test_retrieve(self):
        response = self.client.post('/payment_cards/accounts/loyalty_id/{}'.format(self.scheme.slug),
                                    json.dumps({"payment_cards": [self.payment_card_account_1.token,
                                                                  self.payment_card_account_2.token]}),
                                    content_type='application/json',
                                    **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data, [{
            self.payment_card_account_1.token: self.scheme_answer_1.answer,
            'scheme_account_id': 1,
        }, {
            self.payment_card_account_2.token: self.scheme_answer_2.answer,
            'scheme_account_id': 2,
        }])

    def test_404_scheme_unavailable(self):
        response = self.client.post('/payment_cards/accounts/loyalty_id/{}'.format("unavailable_scheme"),
                                    json.dumps({"payment_cards": [self.payment_card_account_1.token,
                                                                  self.payment_card_account_2.token]}),
                                    content_type='application/json',
                                    **self.auth_headers)
        self.assertEqual(response.status_code, 404)

    def test_invalid_card_token(self):
        response = self.client.post('/payment_cards/accounts/loyalty_id/{}'.format(self.scheme.slug),
                                    json.dumps({"payment_cards": [self.payment_card_account_1.token, 99999]}),
                                    content_type='application/json',
                                    **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data, [{
            'scheme_account_id': 1,
            self.payment_card_account_1.token: self.scheme_answer_1.answer
        }, {'99999': None}])

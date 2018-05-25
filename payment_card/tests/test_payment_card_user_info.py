import json
from rest_framework.test import APITestCase
from hermes import settings
from payment_card.tests import factories as payment_card_factories
from scheme.tests import factories as scheme_factories
from scheme.models import SchemeCredentialQuestion
from user.tests import factories as user_factories


class TestPaymentCardUserInfo(APITestCase):

    @classmethod
    def setUpClass(cls):
        cls.user_1 = user_factories.UserFactory()
        cls.user_2 = user_factories.UserFactory()
        cls.user_3 = user_factories.UserFactory()

        cls.payment_card_account_1 = payment_card_factories.PaymentCardAccountFactory(user=cls.user_1,
                                                                                      psp_token='1144**33',
                                                                                      status=1)
        cls.payment_card_account_2 = payment_card_factories.PaymentCardAccountFactory(user=cls.user_2,
                                                                                      psp_token='3344**11',
                                                                                      status=1)
        cls.payment_card_account_3 = payment_card_factories.PaymentCardAccountFactory(user=cls.user_3,
                                                                                      psp_token='5544**11',
                                                                                      status=0)

        cls.scheme_account_1 = scheme_factories.SchemeAccountFactory(user=cls.user_1)
        cls.scheme = cls.scheme_account_1.scheme
        cls.scheme_account_2 = scheme_factories.SchemeAccountFactory(scheme=cls.scheme, user=cls.user_2)
        cls.scheme_account_3 = scheme_factories.SchemeAccountFactory(scheme=cls.scheme, user=cls.user_3)

        cls.scheme_question = scheme_factories.SchemeCredentialQuestionFactory(scheme=cls.scheme,
                                                                               third_party_identifier=True,
                                                                               options=SchemeCredentialQuestion.LINK)

        cls.scheme_answer_1 = scheme_factories.SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account_1,
                                                                             question=cls.scheme_question)
        cls.scheme_answer_2 = scheme_factories.SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account_2,
                                                                             question=cls.scheme_question)
        cls.scheme_answer_3 = scheme_factories.SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account_3,
                                                                             question=cls.scheme_question)

        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + settings.SERVICE_API_KEY}
        super(TestPaymentCardUserInfo, cls).setUpClass()

    def test_retrieve(self):
        response = self.client.post('/payment_cards/accounts/payment_card_user_info/{}'.format(self.scheme.slug),
                                    json.dumps({"payment_cards": [self.payment_card_account_1.psp_token,
                                                                  self.payment_card_account_2.psp_token,
                                                                  self.payment_card_account_3.psp_token]}),
                                    content_type='application/json',
                                    **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))

        self.assertIn('1144**33', data)
        self.assertEqual(data['1144**33']['user_id'], self.user_1.id)
        self.assertEqual(data['1144**33']['scheme_account_id'], self.scheme_account_1.id)
        self.assertEqual(data['1144**33']['loyalty_id'], self.scheme_answer_1.answer)
        self.assertEqual(data['1144**33']['card_information']['first_six'], str(self.payment_card_account_1.pan_start))
        self.assertEqual(data['1144**33']['card_information']['last_four'], str(self.payment_card_account_1.pan_end))

        self.assertIn('3344**11', data)
        self.assertEqual(data['3344**11']['user_id'], self.user_2.id)
        self.assertEqual(data['3344**11']['scheme_account_id'], self.scheme_account_2.id)
        self.assertEqual(data['3344**11']['loyalty_id'], self.scheme_answer_2.answer)
        self.assertEqual(data['3344**11']['card_information']['first_six'], str(self.payment_card_account_2.pan_start))
        self.assertEqual(data['3344**11']['card_information']['last_four'], str(self.payment_card_account_2.pan_end))

        self.assertIn('5544**11', data)
        self.assertEqual(data['5544**11']['user_id'], self.user_3.id)
        self.assertEqual(data['5544**11']['scheme_account_id'], self.scheme_account_3.id)
        self.assertEqual(data['5544**11']['loyalty_id'], self.scheme_answer_3.answer)
        self.assertNotIn('card_information', data['5544**11'])

    def test_404_scheme_unavailable(self):
        response = self.client.post('/payment_cards/accounts/payment_card_user_info/{}'.format("unavailable_scheme"),
                                    json.dumps({"payment_cards": [self.payment_card_account_1.psp_token,
                                                                  self.payment_card_account_2.psp_token]}),
                                    content_type='application/json',
                                    **self.auth_headers)
        self.assertEqual(response.status_code, 404)

    def test_invalid_card_token(self):
        response = self.client.post('/payment_cards/accounts/payment_card_user_info/{}'.format(self.scheme.slug),
                                    json.dumps({"payment_cards": [self.payment_card_account_1.psp_token, 99999]}),
                                    content_type='application/json',
                                    **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))

        self.assertIn('1144**33', data)
        self.assertEqual(data['1144**33']['user_id'], self.user_1.id)
        self.assertEqual(data['1144**33']['scheme_account_id'], self.scheme_account_1.id)
        self.assertEqual(data['1144**33']['loyalty_id'], self.scheme_answer_1.answer)
        self.assertEqual(data['1144**33']['card_information']['first_six'], str(self.payment_card_account_1.pan_start))
        self.assertEqual(data['1144**33']['card_information']['last_four'], str(self.payment_card_account_1.pan_end))

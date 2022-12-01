import json

import ubiquity.tests.factories
from hermes import settings
from hermes.fixtures.setupdb import set_up_db
from history.utils import GlobalMockAPITestCase
from payment_card.tests import factories as payment_card_factories
from scheme.models import SchemeCredentialQuestion
from scheme.tests import factories as scheme_factories
from ubiquity.models import PaymentCardSchemeEntry
from user.tests import factories as user_factories


class TestPaymentCardUserInfo(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        set_up_db(cls)
        cls.user_1 = user_factories.UserFactory()
        cls.user_2 = user_factories.UserFactory()
        cls.user_3 = user_factories.UserFactory()

        cls.psp_token_1 = "1144**33"
        cls.psp_token_2 = "3344**11"
        cls.psp_token_3 = "5544**11"

        cls.payment_card_account_1 = payment_card_factories.PaymentCardAccountFactory(
            psp_token=cls.psp_token_1, token=cls.psp_token_1, status=1
        )
        cls.payment_card_account_2 = payment_card_factories.PaymentCardAccountFactory(
            psp_token=cls.psp_token_2, token=cls.psp_token_2, status=1
        )
        cls.payment_card_account_3 = payment_card_factories.PaymentCardAccountFactory(
            psp_token=cls.psp_token_3, token=cls.psp_token_3, status=0
        )

        ubiquity.tests.factories.PaymentCardAccountEntryFactory(
            payment_card_account=cls.payment_card_account_1, user=cls.user_1
        )
        ubiquity.tests.factories.PaymentCardAccountEntryFactory(
            payment_card_account=cls.payment_card_account_2, user=cls.user_2
        )
        ubiquity.tests.factories.PaymentCardAccountEntryFactory(
            payment_card_account=cls.payment_card_account_3, user=cls.user_3
        )

        cls.scheme_account_1 = scheme_factories.SchemeAccountFactory()
        cls.scheme = cls.scheme_account_1.scheme
        cls.scheme_account_2 = scheme_factories.SchemeAccountFactory(scheme=cls.scheme)
        cls.scheme_account_3 = scheme_factories.SchemeAccountFactory(scheme=cls.scheme)

        cls.scheme_account_entry_1 = ubiquity.tests.factories.SchemeAccountEntryFactory(
            scheme_account=cls.scheme_account_1, user=cls.user_1
        )
        cls.scheme_account_entry_2 = ubiquity.tests.factories.SchemeAccountEntryFactory(
            scheme_account=cls.scheme_account_2, user=cls.user_2
        )
        cls.scheme_account_entry_3 = ubiquity.tests.factories.SchemeAccountEntryFactory(
            scheme_account=cls.scheme_account_3, user=cls.user_3
        )

        cls.scheme_question = scheme_factories.SchemeCredentialQuestionFactory(
            scheme=cls.scheme, third_party_identifier=True, options=SchemeCredentialQuestion.LINK
        )

        cls.scheme_answer_1 = scheme_factories.SchemeCredentialAnswerFactory(
            question=cls.scheme_question,
            scheme_account_entry=cls.scheme_account_entry_1,
        )
        cls.scheme_answer_2 = scheme_factories.SchemeCredentialAnswerFactory(
            question=cls.scheme_question,
            scheme_account_entry=cls.scheme_account_entry_2,
        )
        cls.scheme_answer_3 = scheme_factories.SchemeCredentialAnswerFactory(
            question=cls.scheme_question,
            scheme_account_entry=cls.scheme_account_entry_3,
        )

        cls.link1_1 = PaymentCardSchemeEntry(
            payment_card_account=cls.payment_card_account_1, scheme_account=cls.scheme_account_1, active_link=True
        )
        cls.link1_1.save()

        cls.link2_2 = PaymentCardSchemeEntry(
            payment_card_account=cls.payment_card_account_2, scheme_account=cls.scheme_account_2, active_link=True
        )
        cls.link2_2.save()

        cls.link3_3 = PaymentCardSchemeEntry(
            payment_card_account=cls.payment_card_account_3, scheme_account=cls.scheme_account_3, active_link=True
        )
        cls.link3_3.save()

        cls.auth_headers = {"HTTP_AUTHORIZATION": "Token " + settings.SERVICE_API_KEY}

    def test_retrieve(self):
        response = self.client.post(
            "/payment_cards/accounts/payment_card_user_info/{}".format(self.scheme.slug),
            json.dumps(
                {
                    "payment_cards": [
                        self.payment_card_account_1.psp_token,
                        self.payment_card_account_2.psp_token,
                        self.payment_card_account_3.psp_token,
                    ]
                }
            ),
            content_type="application/json",
            **self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode("utf-8"))

        self.assertIn(self.psp_token_1, data)
        self.assertEqual(data[self.psp_token_1]["user_id"], self.user_1.id)
        self.assertEqual(data[self.psp_token_1]["scheme_account_id"], self.scheme_account_1.id)
        self.assertEqual(data[self.psp_token_1]["loyalty_id"], self.scheme_answer_1.answer)
        self.assertEqual(
            data[self.psp_token_1]["card_information"]["first_six"], str(self.payment_card_account_1.pan_start)
        )
        self.assertEqual(
            data[self.psp_token_1]["card_information"]["last_four"], str(self.payment_card_account_1.pan_end)
        )
        self.assertEqual(data[self.psp_token_1]["payment_card_account_id"], self.payment_card_account_1.id)

        self.assertIn(self.psp_token_2, data)
        self.assertEqual(data[self.psp_token_2]["user_id"], self.user_2.id)
        self.assertEqual(data[self.psp_token_2]["scheme_account_id"], self.scheme_account_2.id)
        self.assertEqual(data[self.psp_token_2]["loyalty_id"], self.scheme_answer_2.answer)
        self.assertEqual(
            data[self.psp_token_2]["card_information"]["first_six"], str(self.payment_card_account_2.pan_start)
        )
        self.assertEqual(
            data[self.psp_token_2]["card_information"]["last_four"], str(self.payment_card_account_2.pan_end)
        )
        self.assertEqual(data[self.psp_token_2]["payment_card_account_id"], self.payment_card_account_2.id)

        self.assertIn(self.psp_token_3, data)
        self.assertEqual(data[self.psp_token_3]["user_id"], self.user_3.id)
        self.assertEqual(data[self.psp_token_3]["scheme_account_id"], self.scheme_account_3.id)
        self.assertEqual(data[self.psp_token_3]["loyalty_id"], self.scheme_answer_3.answer)
        self.assertNotIn("card_information", data[self.psp_token_3])
        self.assertEqual(data[self.psp_token_3]["payment_card_account_id"], self.payment_card_account_3.id)

    def test_404_scheme_unavailable(self):
        response = self.client.post(
            "/payment_cards/accounts/payment_card_user_info/{}".format("unavailable_scheme"),
            json.dumps(
                {"payment_cards": [self.payment_card_account_1.psp_token, self.payment_card_account_2.psp_token]}
            ),
            content_type="application/json",
            **self.auth_headers
        )
        self.assertEqual(response.status_code, 404)

    def test_invalid_card_token(self):
        response = self.client.post(
            "/payment_cards/accounts/payment_card_user_info/{}".format(self.scheme.slug),
            json.dumps({"payment_cards": [self.payment_card_account_1.psp_token, 99999]}),
            content_type="application/json",
            **self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode("utf-8"))
        self.assertIn(self.psp_token_1, data)
        self.assertEqual(data[self.psp_token_1]["user_id"], self.user_1.id)
        self.assertEqual(data[self.psp_token_1]["scheme_account_id"], self.scheme_account_1.id)
        self.assertEqual(data[self.psp_token_1]["loyalty_id"], self.scheme_answer_1.answer)
        self.assertEqual(
            data[self.psp_token_1]["card_information"]["first_six"], str(self.payment_card_account_1.pan_start)
        )
        self.assertEqual(
            data[self.psp_token_1]["card_information"]["last_four"], str(self.payment_card_account_1.pan_end)
        )

    def test_soft_linking_payment_card1_allSoft(self):
        self.link1_1.active_link = False
        self.link1_1.save()
        self.link2_2.active_link = False
        self.link2_2.save()
        self.link3_3.active_link = False
        self.link3_3.save()

        response = self.client.post(
            "/payment_cards/accounts/payment_card_user_info/{}".format(self.scheme.slug),
            json.dumps(
                {
                    "payment_cards": [
                        self.payment_card_account_1.psp_token,
                        self.payment_card_account_2.psp_token,
                        self.payment_card_account_3.psp_token,
                    ]
                }
            ),
            content_type="application/json",
            **self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode("utf-8"))

        self.assertIn(self.psp_token_1, data)
        self.assertEqual(data[self.psp_token_1]["user_id"], self.user_1.id)
        self.assertEqual(data[self.psp_token_1]["scheme_account_id"], None)
        self.assertEqual(data[self.psp_token_1]["loyalty_id"], None)
        self.assertEqual(
            data[self.psp_token_1]["card_information"]["first_six"], str(self.payment_card_account_1.pan_start)
        )
        self.assertEqual(
            data[self.psp_token_1]["card_information"]["last_four"], str(self.payment_card_account_1.pan_end)
        )
        self.assertEqual(data[self.psp_token_1]["payment_card_account_id"], self.payment_card_account_1.id)

        self.assertIn(self.psp_token_2, data)
        self.assertEqual(data[self.psp_token_2]["user_id"], self.user_2.id)
        self.assertEqual(data[self.psp_token_2]["scheme_account_id"], None)
        self.assertEqual(data[self.psp_token_2]["loyalty_id"], None)
        self.assertEqual(
            data[self.psp_token_2]["card_information"]["first_six"], str(self.payment_card_account_2.pan_start)
        )
        self.assertEqual(
            data[self.psp_token_2]["card_information"]["last_four"], str(self.payment_card_account_2.pan_end)
        )
        self.assertEqual(data[self.psp_token_2]["payment_card_account_id"], self.payment_card_account_2.id)

        self.assertIn(self.psp_token_3, data)
        self.assertEqual(data[self.psp_token_3]["user_id"], self.user_3.id)
        self.assertEqual(data[self.psp_token_3]["scheme_account_id"], None)
        self.assertEqual(data[self.psp_token_3]["loyalty_id"], None)
        self.assertNotIn("card_information", data[self.psp_token_3])
        self.assertEqual(data[self.psp_token_3]["payment_card_account_id"], self.payment_card_account_3.id)

    def test_soft_linking_payment_card_only2_soft(self):
        self.link1_1.active_link = True
        self.link1_1.save()
        self.link2_2.active_link = False
        self.link2_2.save()
        self.link3_3.active_link = True
        self.link3_3.save()

        response = self.client.post(
            "/payment_cards/accounts/payment_card_user_info/{}".format(self.scheme.slug),
            json.dumps(
                {
                    "payment_cards": [
                        self.payment_card_account_1.psp_token,
                        self.payment_card_account_2.psp_token,
                        self.payment_card_account_3.psp_token,
                    ]
                }
            ),
            content_type="application/json",
            **self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode("utf-8"))

        self.assertIn(self.psp_token_1, data)
        self.assertEqual(data[self.psp_token_1]["user_id"], self.user_1.id)
        self.assertEqual(data[self.psp_token_1]["scheme_account_id"], self.scheme_account_1.id)
        self.assertEqual(data[self.psp_token_1]["loyalty_id"], self.scheme_answer_1.answer)
        self.assertEqual(
            data[self.psp_token_1]["card_information"]["first_six"], str(self.payment_card_account_1.pan_start)
        )
        self.assertEqual(
            data[self.psp_token_1]["card_information"]["last_four"], str(self.payment_card_account_1.pan_end)
        )
        self.assertEqual(data[self.psp_token_1]["payment_card_account_id"], self.payment_card_account_1.id)

        self.assertIn(self.psp_token_2, data)
        self.assertEqual(data[self.psp_token_2]["user_id"], self.user_2.id)
        self.assertEqual(data[self.psp_token_2]["scheme_account_id"], None)
        self.assertEqual(data[self.psp_token_2]["loyalty_id"], None)
        self.assertEqual(
            data[self.psp_token_2]["card_information"]["first_six"], str(self.payment_card_account_2.pan_start)
        )
        self.assertEqual(
            data[self.psp_token_2]["card_information"]["last_four"], str(self.payment_card_account_2.pan_end)
        )
        self.assertEqual(data[self.psp_token_2]["payment_card_account_id"], self.payment_card_account_2.id)

        self.assertIn(self.psp_token_3, data)
        self.assertEqual(data[self.psp_token_3]["user_id"], self.user_3.id)
        self.assertEqual(data[self.psp_token_3]["scheme_account_id"], self.scheme_account_3.id)
        self.assertEqual(data[self.psp_token_3]["loyalty_id"], self.scheme_answer_3.answer)
        self.assertNotIn("card_information", data[self.psp_token_3])
        self.assertEqual(data[self.psp_token_3]["payment_card_account_id"], self.payment_card_account_3.id)

    def test_soft_linking_payment_card_only_2active(self):
        """
        Link is none since different user for payment card and membership card
        """
        self.link1_1.active_link = False
        self.link1_1.save()
        self.link2_2.active_link = True
        self.link2_2.save()
        self.link3_3.active_link = False
        self.link3_3.save()

        response = self.client.post(
            "/payment_cards/accounts/payment_card_user_info/{}".format(self.scheme.slug),
            json.dumps(
                {
                    "payment_cards": [
                        self.payment_card_account_1.psp_token,
                        self.payment_card_account_2.psp_token,
                        self.payment_card_account_3.psp_token,
                    ]
                }
            ),
            content_type="application/json",
            **self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode("utf-8"))

        self.assertIn(self.psp_token_1, data)
        self.assertEqual(data[self.psp_token_1]["user_id"], self.user_1.id)
        self.assertEqual(data[self.psp_token_1]["scheme_account_id"], None)
        self.assertEqual(data[self.psp_token_1]["loyalty_id"], None)
        self.assertEqual(
            data[self.psp_token_1]["card_information"]["first_six"], str(self.payment_card_account_1.pan_start)
        )
        self.assertEqual(
            data[self.psp_token_1]["card_information"]["last_four"], str(self.payment_card_account_1.pan_end)
        )
        self.assertEqual(data[self.psp_token_1]["payment_card_account_id"], self.payment_card_account_1.id)

        self.assertIn(self.psp_token_2, data)
        self.assertEqual(data[self.psp_token_2]["user_id"], self.user_2.id)
        self.assertEqual(data[self.psp_token_2]["scheme_account_id"], self.scheme_account_2.id)
        self.assertEqual(data[self.psp_token_2]["loyalty_id"], self.scheme_answer_2.answer)
        self.assertEqual(
            data[self.psp_token_2]["card_information"]["first_six"], str(self.payment_card_account_2.pan_start)
        )
        self.assertEqual(
            data[self.psp_token_2]["card_information"]["last_four"], str(self.payment_card_account_2.pan_end)
        )
        self.assertEqual(data[self.psp_token_2]["payment_card_account_id"], self.payment_card_account_2.id)

        self.assertIn(self.psp_token_3, data)
        self.assertEqual(data[self.psp_token_3]["user_id"], self.user_3.id)
        self.assertEqual(data[self.psp_token_3]["scheme_account_id"], None)
        self.assertEqual(data[self.psp_token_3]["loyalty_id"], None)
        self.assertNotIn("card_information", data[self.psp_token_3])
        self.assertEqual(data[self.psp_token_3]["payment_card_account_id"], self.payment_card_account_3.id)

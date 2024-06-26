from unittest import mock
from unittest.mock import patch

from django.conf import settings
from django.utils import timezone
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList

import ubiquity.tests.factories
from common.models import Image
from history.utils import GlobalMockAPITestCase
from payment_card.models import AuthTransaction, PaymentCardAccount
from payment_card.tests import factories
from ubiquity.tests.factories import PaymentCardSchemeEntryFactory, SchemeAccountEntryFactory
from user.models import ClientApplication, Organisation
from user.tests.factories import UserFactory


class TestPaymentCardImages(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        user = UserFactory()
        cls.auth_headers = {"HTTP_AUTHORIZATION": "Token " + user.create_token()}
        cls.image = factories.PaymentCardImageFactory(
            status=Image.DRAFT,
            start_date=timezone.now() - timezone.timedelta(hours=1),
            end_date=timezone.now() + timezone.timedelta(hours=1),
        )

    def test_no_draft_images_in_payment_cards_list(self):
        resp = self.client.get("/payment_cards", **self.auth_headers)
        our_payment_card = next(s for s in resp.json() if s["slug"] == self.image.payment_card.slug)
        self.assertEqual(0, len(our_payment_card["images"]))

        self.image.status = Image.PUBLISHED
        self.image.save()

        resp = self.client.get("/payment_cards", **self.auth_headers)
        our_payment_card = next(s for s in resp.json() if s["slug"] == self.image.payment_card.slug)
        self.assertEqual(1, len(our_payment_card["images"]))


class TestPaymentCard(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.payment_card_account = factories.PaymentCardAccountFactory(
            psp_token="token", status=PaymentCardAccount.PENDING
        )
        cls.payment_card = cls.payment_card_account.payment_card
        cls.payment_card_account_entry = ubiquity.tests.factories.PaymentCardAccountEntryFactory(
            payment_card_account=cls.payment_card_account
        )
        cls.user = cls.payment_card_account_entry.user
        cls.issuer = cls.payment_card_account.issuer
        cls.auth_headers = {"HTTP_AUTHORIZATION": "Token " + cls.user.create_token()}
        cls.auth_service_headers = {"HTTP_AUTHORIZATION": "Token " + settings.SERVICE_API_KEY}
        cls.payment_card_image = factories.PaymentCardAccountImageFactory()

    def test_payment_card_account_query(self):
        resp = self.client.get(
            "/payment_cards/accounts/query" f"?payment_card__slug={self.payment_card.slug}&user_set__id={self.user.id}",
            **self.auth_service_headers,
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json()[0]["id"], self.payment_card_account.id)

    def test_payment_card_account_bad_query(self):
        resp = self.client.get(
            "/payment_cards/accounts/query" "?payment_card=what&user_set__id=no", **self.auth_service_headers
        )
        self.assertEqual(400, resp.status_code)

    def test_payment_card_account_query_no_results(self):
        resp = self.client.get(
            "/payment_cards/accounts/query" "?payment_card__slug=scheme-that-doesnt-exist", **self.auth_service_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(0, len(resp.json()))

    def test_payment_card_list(self):
        response = self.client.get("/payment_cards", **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnList)
        self.assertTrue(response.data)

    def test_list_payment_card_accounts(self):
        response = self.client.get("/payment_cards/accounts", **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), list)

        self.assertIn("currency_code", response.data[0])
        self.assertIn("status_name", response.data[0])
        self.assertNotIn("psp_token", response.data[0])
        self.assertNotIn("token", response.data[0])

    def test_get_payment_card_account(self):
        response = self.client.get(f"/payment_cards/accounts/{self.payment_card_account.id}", **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data["id"], self.payment_card_account.id)
        self.assertNotIn("psp_token", response.data)
        self.assertNotIn("token", response.data)
        self.assertEqual(response.data["status_name"], "pending")

    def test_patch_payment_card_account(self):
        response = self.client.patch(
            f"/payment_cards/accounts/{self.payment_card_account.id}", data={"pan_start": "987678"}, **self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data["pan_start"], "987678")

    def test_patch_payment_card_cannot_change_scheme(self):
        payment_card_2 = factories.PaymentCardFactory(name="sommet", slug="sommet")
        response = self.client.patch(
            f"/payment_cards/accounts/{self.payment_card_account.id}",
            data={"payment_card": payment_card_2.id},
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"payment_card": ["Cannot change payment card for payment card account."]})

    def test_put_payment_card_cannot_change_scheme(self):
        payment_card_2 = factories.PaymentCardFactory(name="sommet", slug="sommet")
        response = self.client.put(
            f"/payment_cards/accounts/{self.payment_card_account.id}",
            data={"issuer": self.issuer.id, "pan_end": "0000", "payment_card": payment_card_2.id},
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"payment_card": ["Cannot change payment card for payment card account."]})

    @patch("payment_card.views.to_data_warehouse")
    def test_put_payment_card_account_status(self, mock_to_warehouse):
        response = self.client.put(
            "/payment_cards/accounts/status",
            data={"status": 1, "id": self.payment_card_account.id},
            **self.auth_service_headers,
        )

        self.assertTrue(mock_to_warehouse.called)
        passed_to_mock = mock_to_warehouse.call_args_list[0][0][0]
        self.assertEqual(passed_to_mock["event_type"], "payment.account.status.change")
        self.assertEqual(passed_to_mock["origin"], "scheme.callback")
        self.assertEqual(passed_to_mock["channel"], self.user.client.clientapplicationbundle_set.first().bundle_id)
        self.assertEqual(passed_to_mock["internal_user_ref"], self.user.id)
        self.assertEqual(passed_to_mock["from_status"], 0)
        self.assertEqual(passed_to_mock["to_status"], 1)
        self.assertEqual(passed_to_mock["payment_account_id"], self.payment_card_account.id)
        self.assertEqual(passed_to_mock["fingerprint"], self.payment_card_account.fingerprint)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.payment_card_account.id)
        self.assertEqual(response.data["status"], 1)

    def test_put_invalid_payment_card_account_status(self):
        response = self.client.put(
            "/payment_cards/accounts/status",
            data={"status": 9999, "id": self.payment_card_account.id},
            **self.auth_service_headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data[0], "Invalid status code sent.")

    @mock.patch("payment_card.metis.metis_delete_cards_and_activations", autospec=True)
    def test_delete_payment_card_accounts(self, mock_metis):
        response = self.client.delete(f"/payment_cards/accounts/{self.payment_card_account.id}", **self.auth_headers)

        self.assertEqual(response.status_code, 204)
        response = self.client.get(f"/payment_cards/accounts/{self.payment_card_account.id}", **self.auth_headers)

        self.assertEqual(response.status_code, 404)
        # The stub is called indirectly via the View so we can only verify the stub has been called
        self.assertTrue(mock_metis.delay.called)

    def test_cant_delete_other_payment_card_account(self):
        payment_card = factories.PaymentCardAccountFactory(payment_card=self.payment_card)

        response = self.client.delete(f"/payment_cards/accounts/{payment_card.id}", **self.auth_headers)
        self.assertEqual(response.status_code, 404)

    def test_get_payment_card_scheme_accounts(self):
        token = "test_token_123"
        user = UserFactory()
        sae = SchemeAccountEntryFactory(user=user)
        pca = factories.PaymentCardAccountFactory(psp_token=token, token=token, payment_card=self.payment_card)
        ubiquity.tests.factories.PaymentCardAccountEntryFactory(user=user, payment_card_account=pca)
        PaymentCardSchemeEntryFactory(payment_card_account=pca, scheme_account=sae.scheme_account)

        response = self.client.get(f"/payment_cards/scheme_accounts/{token}", **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(len(response.data[0]), 2)
        keys = list(response.data[0].keys())
        self.assertEqual(keys[0], "scheme_id")
        self.assertEqual(keys[1], "scheme_account_id")


class TestAuthTransactions(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.auth_service_headers = {"HTTP_AUTHORIZATION": "Token " + settings.SERVICE_API_KEY}
        cls.payment_card_account = factories.PaymentCardAccountFactory(
            psp_token="234rghjcewerg4gf3ef23v", token="234rghjcewerg4gf3ef23v"
        )

    def test_create_auth_transaction_endpoint(self):
        payload = {
            "time": "2018-05-24 14:54:10.825035+01:00",
            "amount": 1260,
            "mid": "1",
            "third_party_id": "1",
            "payment_card_token": "234rghjcewerg4gf3ef23v",
            "auth_code": "1",
            "currency_code": "GBP",
        }

        expected_resp = {
            "time": "2018-05-24T14:54:10.825035+01:00",
            "amount": 1260,
            "mid": "1",
            "third_party_id": "1",
            "auth_code": "1",
            "currency_code": "GBP",
        }
        self.assertIsNone(AuthTransaction.objects.filter(payment_card_account=self.payment_card_account.pk).first())

        resp = self.client.post("/payment_cards/auth_transaction", payload, **self.auth_service_headers)

        self.assertEqual(resp.status_code, 201)
        self.assertDictEqual(resp.data, expected_resp)
        self.assertIsNotNone(AuthTransaction.objects.filter(payment_card_account=self.payment_card_account.pk).first())

    def test_create_auth_transaction_endpoint_no_auth_code(self):
        payload = {
            "time": "2018-05-24 14:54:10.825035+01:00",
            "amount": 1260,
            "mid": "1",
            "third_party_id": "1",
            "payment_card_token": "234rghjcewerg4gf3ef23v",
            "currency_code": "GBP",
        }

        expected_resp = {
            "time": "2018-05-24T14:54:10.825035+01:00",
            "amount": 1260,
            "mid": "1",
            "third_party_id": "1",
            "auth_code": "",
            "currency_code": "GBP",
        }
        self.assertIsNone(AuthTransaction.objects.filter(payment_card_account=self.payment_card_account.pk).first())

        resp = self.client.post("/payment_cards/auth_transaction", payload, **self.auth_service_headers)

        self.assertEqual(resp.status_code, 201)
        self.assertDictEqual(resp.data, expected_resp)
        self.assertIsNotNone(AuthTransaction.objects.filter(payment_card_account=self.payment_card_account.pk).first())

    def test_list_payment_card_client_apps(self):
        amex = Organisation.objects.create(name="American Express")
        mc = Organisation.objects.create(name="Master Card")

        ClientApplication.objects.create(name="Amex Auth Transactions", organisation=amex)
        ClientApplication.objects.create(name="MC Auth Transactions", organisation=mc)

        resp = self.client.get("/payment_cards/client_apps", **self.auth_service_headers)

        self.assertEqual(200, resp.status_code)
        self.assertTrue(len(resp.data), 2)

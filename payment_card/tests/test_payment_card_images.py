from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from common.models import Image
from history.utils import GlobalMockAPITestCase
from payment_card.serializers import PaymentCardAccountSerializer
from payment_card.tests.factories import PaymentCardAccountImageFactory, PaymentCardImageFactory
from ubiquity.tests.factories import PaymentCardAccountEntryFactory


class TestPaymentCardAccountImages(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.payment_card_account_entry = PaymentCardAccountEntryFactory()
        cls.payment_card_account = cls.payment_card_account_entry.payment_card_account
        cls.payment_card_account_image = PaymentCardAccountImageFactory(
            image_type_code=2,
            status=Image.PUBLISHED,
            start_date=timezone.now() - timezone.timedelta(hours=1),
            end_date=timezone.now() + timezone.timedelta(hours=1),
        )
        cls.payment_card_account_image.payment_card_accounts.add(cls.payment_card_account)

        cls.payment_card_images = [
            PaymentCardImageFactory(image_type_code=1, payment_card=cls.payment_card_account.payment_card),
            PaymentCardImageFactory(image_type_code=2, payment_card=cls.payment_card_account.payment_card),
            PaymentCardImageFactory(image_type_code=3, payment_card=cls.payment_card_account.payment_card),
        ]

        cls.user = cls.payment_card_account_entry.user
        cls.auth_headers = {"HTTP_AUTHORIZATION": "Token " + cls.user.create_token()}

    def test_image_property(self):
        serializer = PaymentCardAccountSerializer()
        images = serializer.get_images(self.payment_card_account)
        our_image = next((i for i in images if i["image"] == self.payment_card_account_image.image.url), None)
        self.assertIsNotNone(our_image)

    def test_CSV_upload(self):
        csv_file = SimpleUploadedFile("file.csv", content=b"", content_type="text/csv")
        response = self.client.post(
            "/payment_cards/csv_upload",
            {"payment_card": self.payment_card_account.payment_card.name, "emails": csv_file},
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)

    def test_images_have_object_type_properties(self):
        serializer = PaymentCardAccountSerializer()
        images = serializer.get_images(self.payment_card_account)

        self.assertEqual(images[0]["object_type"], "payment_card_account_image")
        self.assertEqual(images[1]["object_type"], "payment_card_image")
        self.assertEqual(images[2]["object_type"], "payment_card_image")

    def test_images_in_payment_card_response(self):
        resp = self.client.get("/payment_cards", **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        json = resp.json()
        self.assertIn("images", json[0])
        self.assertIsInstance(json[0]["images"], list)

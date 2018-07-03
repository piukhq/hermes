from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from payment_card.models import PaymentCardAccountImage
from payment_card.tests import factories


class TestCSVUpload(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.payment_card_account = factories.PaymentCardAccountFactory(psp_token='token')
        cls.payment_card_account_entry = factories.PaymentCardAccountEntryFactory(
            payment_card_account=cls.payment_card_account)
        cls.payment_card = cls.payment_card_account.payment_card
        cls.user = cls.payment_card_account_entry.user
        cls.issuer = cls.payment_card_account.issuer
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}

        super(TestCSVUpload, cls).setUpClass()

    def test_CSV_upload(self):
        csv_file = SimpleUploadedFile("file.csv", content=bytes(self.user.email, 'utf-8'), content_type="text/csv")

        self.client.post('/payment_cards/csv_upload', {'scheme': self.payment_card.id, 'emails': csv_file},
                         **self.auth_headers)

        image = PaymentCardAccountImage.all_objects.filter(payment_card=self.payment_card).first()
        self.assertIsNotNone(image)

        account = image.payment_card_accounts.filter(pk=self.payment_card_account.id)
        self.assertIsNotNone(account)

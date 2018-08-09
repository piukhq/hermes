from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from common.models import Image
from payment_card.tests.factories import PaymentCardAccountImageFactory, PaymentCardImageFactory
from ubiquity.tests.factories import PaymentCardAccountEntryFactory
from ubiquity.tests.property_token import GenerateJWToken
from user.tests.factories import UserFactory, ClientApplicationBundleFactory, ClientApplicationFactory, \
    OrganisationFactory


class TestPaymentCardAccountImages(APITestCase):
    @classmethod
    def setUpClass(cls):
        organisation = OrganisationFactory(name='set up authentication')
        client = ClientApplicationFactory(organisation=organisation, name='set up client application')
        bundle = ClientApplicationBundleFactory(bundle_id='test.auth.fake', client=client)
        email = 'test@user.com'
        cls.user = UserFactory(email=email, client=client)

        cls.payment_card_account_entry = PaymentCardAccountEntryFactory(user=cls.user)
        cls.payment_card_account = cls.payment_card_account_entry.payment_card_account
        cls.payment_card_account_image = PaymentCardAccountImageFactory(
            image_type_code=2,
            status=Image.PUBLISHED,
            start_date=timezone.now() - timezone.timedelta(hours=1),
            end_date=timezone.now() + timezone.timedelta(hours=1))
        cls.payment_card_account_image.payment_card_accounts.add(cls.payment_card_account)

        cls.payment_card_images = [
            PaymentCardImageFactory(image_type_code=1, payment_card=cls.payment_card_account.payment_card),
            PaymentCardImageFactory(image_type_code=2, payment_card=cls.payment_card_account.payment_card),
            PaymentCardImageFactory(image_type_code=3, payment_card=cls.payment_card_account.payment_card),
        ]

        token = GenerateJWToken(client.client_id, client.secret, bundle.bundle_id, email).get_token()
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Bearer {}'.format(token)}
        super().setUpClass()

    def test_images_in_payment_card_response(self):
        resp = self.client.get(reverse('payment-cards'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        json = resp.json()
        self.assertIn('images', json[0])
        self.assertIsInstance(json[0]['images'], list)

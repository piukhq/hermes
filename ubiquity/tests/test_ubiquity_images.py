from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from scheme.models import SchemeBundleAssociation
from common.models import Image
from payment_card.tests.factories import PaymentCardAccountImageFactory, PaymentCardImageFactory
from scheme.tests.factories import SchemeAccountImageFactory, SchemeImageFactory, SchemeBundleAssociationFactory
from ubiquity.versioning.base.serializers import MembershipTransactionsMixin
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory
from ubiquity.tests.property_token import GenerateJWToken
from user.tests.factories import (ClientApplicationBundleFactory, ClientApplicationFactory, OrganisationFactory,
                                  UserFactory)


class TestPaymentCardAccountImages(APITestCase):
    @classmethod
    def setUpClass(cls):
        organisation = OrganisationFactory(name='set up authentication')
        client = ClientApplicationFactory(organisation=organisation, name='set up client application')
        bundle = ClientApplicationBundleFactory(bundle_id='test.auth.fake', client=client)
        external_id = 'test@user.com'
        cls.user = UserFactory(external_id=external_id, client=client, email=external_id)

        # Payment cards
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

        # Membership Cards
        cls.membership_card_account_entry = SchemeAccountEntryFactory(user=cls.user)
        cls.membership_card_account = cls.membership_card_account_entry.scheme_account
        cls.membership_card_account_image = SchemeAccountImageFactory(
            image_type_code=2,
            status=Image.PUBLISHED,
            start_date=timezone.now() - timezone.timedelta(hours=1),
            end_date=timezone.now() + timezone.timedelta(hours=1))
        cls.membership_card_account_image.scheme_accounts.add(cls.membership_card_account)

        cls.membership_card_images = [
            SchemeImageFactory(image_type_code=1, scheme=cls.membership_card_account.scheme),
            SchemeImageFactory(image_type_code=2, scheme=cls.membership_card_account.scheme),
            SchemeImageFactory(image_type_code=3, scheme=cls.membership_card_account.scheme),
        ]

        cls.scheme_bundle_association = SchemeBundleAssociationFactory(scheme=cls.membership_card_account.scheme,
                                                                       bundle=bundle,
                                                                       status=SchemeBundleAssociation.ACTIVE)

        token = GenerateJWToken(client.organisation.name, client.secret, bundle.bundle_id, external_id).get_token()
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Bearer {}'.format(token)}
        super().setUpClass()

    def test_images_in_payment_card_response(self):
        resp = self.client.get(reverse('payment-cards'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        json = resp.json()
        self.assertIn('images', json[0])
        self.assertIsInstance(json[0]['images'], list)

    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch('ubiquity.serializers.async_balance', autospec=True)
    def test_images_in_membership_card_response(self, mock_get_midas_balance, _):
        resp = self.client.get(reverse('membership-cards'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        json = resp.json()
        self.assertIn('images', json[0])
        self.assertIsInstance(json[0]['images'], list)

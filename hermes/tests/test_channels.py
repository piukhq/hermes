import time
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.conf import settings

from hermes.channels import Permit
from payment_card.tests.factories import PaymentCardAccountFactory
from scheme.models import SchemeBundleAssociation, Scheme
from scheme.tests.factories import (SchemeFactory, SchemeBundleAssociationFactory, SchemeAccountFactory)
from ubiquity.tests.factories import SchemeAccountEntryFactory, PaymentCardAccountEntryFactory
from ubiquity.tests.property_token import GenerateJWToken
from user.models import Organisation, ClientApplication, ClientApplicationBundle
from user.tests.factories import (ClientApplicationBundleFactory, ClientApplicationFactory, OrganisationFactory,
                                  UserFactory)


class TestPermit(TestCase):

    def setUp(self):
        self.BINK_CLIENT_ID = 'ffhfhfhfhplqszzccgbnmml987tvgcxznnkn'
        self.BINK_BUNDLE_ID = 'com.bink.wallet'
        self.bink_organisation = OrganisationFactory(name='loyalty')
        self.bink_client_app = ClientApplicationFactory(organisation=self.bink_organisation,
                                                        name='loyalty client application',
                                                        client_id=self.BINK_CLIENT_ID)

        self.bink_bundle = ClientApplicationBundleFactory(client=self.bink_client_app, bundle_id=self.BINK_BUNDLE_ID)
        self.bink_scheme = SchemeFactory()
        self.bink_scheme_bundle_association = SchemeBundleAssociationFactory(scheme=self.bink_scheme,
                                                                             bundle=self.bink_bundle,
                                                                             status=SchemeBundleAssociation.INACTIVE)

        self.UBIQUITY_CLIENT_ID = 'cjcdcjdji8oupisqwie0kjpkapkdsks21efjeopgi'
        self.UBIQUITY_BUNDLE_ID = 'com.barclays.test'
        self.UBIQUITY_ORG = 'barclays'
        self.ubiquity_organisation = OrganisationFactory(name=self.UBIQUITY_ORG)
        self.ubiquity_client_app = ClientApplicationFactory(organisation=self.ubiquity_organisation,
                                                            name='ubiquity client application',
                                                            client_id=self.UBIQUITY_CLIENT_ID)

        self.ubiquity_bundle = ClientApplicationBundleFactory(bundle_id=self.UBIQUITY_BUNDLE_ID,
                                                              client=self.ubiquity_client_app)

        self.ubiquity_scheme = SchemeFactory()
        self.ubiquity_scheme_bundle_association = \
            SchemeBundleAssociationFactory(scheme=self.ubiquity_scheme,
                                           bundle=self.ubiquity_bundle,
                                           status=SchemeBundleAssociation.ACTIVE)

    def set_status(self, assoc, status):
        assoc.status = status
        assoc.save()
        return Permit(self.BINK_BUNDLE_ID, self.bink_client_app)

    def set_ubiquity_status(self, assoc, status):
        assoc.status = status
        assoc.save()
        return Permit(self.UBIQUITY_BUNDLE_ID, organisation_name=self.ubiquity_organisation, ubiquity=True)

    def test_is_scheme_active(self):
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertTrue(permit.is_scheme_active(self.bink_scheme))
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertFalse(permit.is_scheme_active(self.bink_scheme))
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertFalse(permit.is_scheme_active(self.bink_scheme))

        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertTrue(permit.is_scheme_active(self.ubiquity_scheme))
        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertFalse(permit.is_scheme_active(self.ubiquity_scheme))
        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertFalse(permit.is_scheme_active(self.ubiquity_scheme))

    def test_is_scheme_suspended(self):
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertFalse(permit.is_scheme_suspended(self.bink_scheme))
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertFalse(permit.is_scheme_suspended(self.bink_scheme))
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertTrue(permit.is_scheme_suspended(self.bink_scheme))

        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertFalse(permit.is_scheme_suspended(self.ubiquity_scheme))
        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertFalse(permit.is_scheme_suspended(self.ubiquity_scheme))
        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertFalse(permit.is_scheme_suspended(self.ubiquity_scheme))

    def test_is_scheme_available(self):
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertTrue(permit.is_scheme_available(self.bink_scheme))
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertFalse(permit.is_scheme_available(self.bink_scheme))
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertTrue(permit.is_scheme_available(self.bink_scheme))

        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertTrue(permit.is_scheme_available(self.ubiquity_scheme))
        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertFalse(permit.is_scheme_available(self.ubiquity_scheme))
        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertFalse(permit.is_scheme_available(self.ubiquity_scheme))

    def test_get_scheme_name(self):
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertEqual(permit.scheme_status_name(self.bink_scheme), 'active')
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertEqual(permit.scheme_status_name(self.bink_scheme), 'in_active')
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertEqual(permit.scheme_status_name(self.bink_scheme), 'suspended')

    def test_get_scheme_status(self):
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertEqual(permit.scheme_status(self.bink_scheme), 0)
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertEqual(permit.scheme_status(self.bink_scheme), 2)
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertEqual(permit.scheme_status(self.bink_scheme), 1)

    def test_scheme_query_both_active(self):
        bink_permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        ubiquity_permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association,
                                                   SchemeBundleAssociation.ACTIVE)

        bink_query = bink_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(bink_query), 1)
        self.assertEqual(self.bink_scheme.id, bink_query[0].id)

        ubiquity_query = ubiquity_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(ubiquity_query), 1)
        self.assertEqual(self.ubiquity_scheme.id, ubiquity_query[0].id)

    def test_scheme_query_bink_active_ubiquity_inactive(self):
        bink_permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        ubiquity_permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association,
                                                   SchemeBundleAssociation.INACTIVE)

        bink_query = bink_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(bink_query), 1)
        self.assertEqual(self.bink_scheme.id, bink_query[0].id)

        ubiquity_query = ubiquity_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(ubiquity_query), 0)

    def test_scheme_query_bink_active_ubiquity_suspended(self):
        bink_permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        ubiquity_permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association,
                                                   SchemeBundleAssociation.SUSPENDED)

        bink_query = bink_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(bink_query), 1)
        self.assertEqual(self.bink_scheme.id, bink_query[0].id)

        ubiquity_query = ubiquity_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(ubiquity_query), 0)

    def test_scheme_query_bink_suspended_ubiquity_active(self):
        bink_permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        ubiquity_permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association,
                                                   SchemeBundleAssociation.ACTIVE)

        bink_query = bink_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(bink_query), 1)
        self.assertEqual(self.bink_scheme.id, bink_query[0].id)

        ubiquity_query = ubiquity_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(ubiquity_query), 1)
        self.assertEqual(self.ubiquity_scheme.id, ubiquity_query[0].id)

    def test_scheme_query_bink_inactive_ubiquity_active(self):
        bink_permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        ubiquity_permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association,
                                                   SchemeBundleAssociation.ACTIVE)

        bink_query = bink_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(bink_query), 0)

        ubiquity_query = ubiquity_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(ubiquity_query), 1)
        self.assertEqual(self.ubiquity_scheme.id, ubiquity_query[0].id)


class TestPermitSharedScheme(TestCase):

    def setUp(self):
        self.BINK_CLIENT_ID = 'ffhfhfhfhplqszzccgbnmml987tvgcxznnkn'
        self.BINK_BUNDLE_ID = 'com.bink.wallet'
        self.bink_organisation = OrganisationFactory(name='loyalty')
        self.bink_client_app = ClientApplicationFactory(organisation=self.bink_organisation,
                                                        name='loyalty client application',
                                                        client_id=self.BINK_CLIENT_ID)

        self.bink_bundle = ClientApplicationBundleFactory(client=self.bink_client_app, bundle_id=self.BINK_BUNDLE_ID)

        self.scheme = SchemeFactory()
        self.bink_scheme_bundle_association = SchemeBundleAssociationFactory(scheme=self.scheme,
                                                                             bundle=self.bink_bundle,
                                                                             status=SchemeBundleAssociation.INACTIVE)

        self.UBIQUITY_CLIENT_ID = 'cjcdcjdji8oupisqwie0kjpkapkdsks21efjeopgi'
        self.UBIQUITY_BUNDLE_ID = 'com.barclays.test'
        self.UBIQUITY_ORG = 'barclays'
        self.ubiquity_organisation = OrganisationFactory(name=self.UBIQUITY_ORG)
        self.ubiquity_client_app = ClientApplicationFactory(organisation=self.ubiquity_organisation,
                                                            name='ubiquity client application',
                                                            client_id=self.UBIQUITY_CLIENT_ID)

        self.ubiquity_bundle = ClientApplicationBundleFactory(bundle_id=self.UBIQUITY_BUNDLE_ID,
                                                              client=self.ubiquity_client_app)

        self.ubiquity_scheme_bundle_association = \
            SchemeBundleAssociationFactory(scheme=self.scheme,
                                           bundle=self.ubiquity_bundle,
                                           status=SchemeBundleAssociation.ACTIVE)

    def set_status(self, assoc, status):
        assoc.status = status
        assoc.save()
        return Permit(self.BINK_BUNDLE_ID, self.bink_client_app)

    def set_ubiquity_status(self, assoc, status):
        assoc.status = status
        assoc.save()
        return Permit(self.UBIQUITY_BUNDLE_ID, organisation_name=self.ubiquity_organisation, ubiquity=True)

    def test_is_scheme_active(self):
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertTrue(permit.is_scheme_active(self.scheme))
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertFalse(permit.is_scheme_active(self.scheme))
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertFalse(permit.is_scheme_active(self.scheme))

        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertTrue(permit.is_scheme_active(self.scheme))
        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertFalse(permit.is_scheme_active(self.scheme))
        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertFalse(permit.is_scheme_active(self.scheme))

    def test_is_scheme_suspended(self):
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertFalse(permit.is_scheme_suspended(self.scheme))
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertFalse(permit.is_scheme_suspended(self.scheme))
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertTrue(permit.is_scheme_suspended(self.scheme))

        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertFalse(permit.is_scheme_suspended(self.scheme))
        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertFalse(permit.is_scheme_suspended(self.scheme))
        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertFalse(permit.is_scheme_suspended(self.scheme))

    def test_is_scheme_available(self):
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertTrue(permit.is_scheme_available(self.scheme))
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertFalse(permit.is_scheme_available(self.scheme))
        permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertTrue(permit.is_scheme_available(self.scheme))

        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        self.assertTrue(permit.is_scheme_available(self.scheme))
        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        self.assertFalse(permit.is_scheme_available(self.scheme))
        permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        self.assertFalse(permit.is_scheme_available(self.scheme))

    def test_scheme_query_both_active(self):
        bink_permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        ubiquity_permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association,
                                                   SchemeBundleAssociation.ACTIVE)

        bink_query = bink_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(bink_query), 1)
        self.assertEqual(self.scheme.id, bink_query[0].id)

        ubiquity_query = ubiquity_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(ubiquity_query), 1)
        self.assertEqual(self.scheme.id, ubiquity_query[0].id)

    def test_scheme_query_bink_active_ubiquity_inactive(self):
        bink_permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        ubiquity_permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association,
                                                   SchemeBundleAssociation.INACTIVE)

        bink_query = bink_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(bink_query), 1)
        self.assertEqual(self.scheme.id, bink_query[0].id)

        ubiquity_query = ubiquity_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(ubiquity_query), 0)

    def test_scheme_query_bink_active_ubiquity_suspended(self):
        bink_permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        ubiquity_permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association,
                                                   SchemeBundleAssociation.SUSPENDED)

        bink_query = bink_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(bink_query), 1)
        self.assertEqual(self.scheme.id, bink_query[0].id)

        ubiquity_query = ubiquity_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(ubiquity_query), 0)

    def test_scheme_query_bink_suspended_ubiquity_active(self):
        bink_permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.SUSPENDED)
        ubiquity_permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association,
                                                   SchemeBundleAssociation.ACTIVE)

        bink_query = bink_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(bink_query), 1)
        self.assertEqual(self.scheme.id, bink_query[0].id)

        ubiquity_query = ubiquity_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(ubiquity_query), 1)
        self.assertEqual(self.scheme.id, ubiquity_query[0].id)

    def test_scheme_query_bink_inactive_ubiquity_active(self):
        bink_permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.INACTIVE)
        ubiquity_permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association,
                                                   SchemeBundleAssociation.ACTIVE)

        bink_query = bink_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(bink_query), 0)

        ubiquity_query = ubiquity_permit.scheme_query(Scheme.objects)
        self.assertEquals(len(ubiquity_query), 1)
        self.assertEqual(self.scheme.id, ubiquity_query[0].id)


class TestInternalService(TestCase):
    def setUp(self):
        self.bink_org = Organisation.objects.get(name='Loyalty Angels')
        self.internal_service_client = ClientApplication.objects.get(organisation=self.bink_org, name='Daedalus')
        self.internal_service_bundle = ClientApplicationBundle.objects.get(bundle_id=settings.INTERNAL_SERVICE_BUNDLE)

        self.other_org = OrganisationFactory(name='Other Organisation')
        self.other_client = ClientApplicationFactory(organisation=self.other_org)
        self.other_bundle = ClientApplicationBundleFactory(client=self.other_client)

        self.internal_service_id = 'external_id@testbink.com'
        other_external_id = 'someotherexternalid@testbink.com'
        self.bink_user = UserFactory(client=self.internal_service_client, external_id=self.internal_service_id)
        self.other_user = UserFactory(client=self.other_client, external_id=other_external_id)

        self.scheme = SchemeFactory()

        SchemeBundleAssociationFactory(scheme=self.scheme,
                                       bundle=self.other_bundle,
                                       status=SchemeBundleAssociation.ACTIVE)

        self.scheme_account_1 = SchemeAccountFactory(scheme=self.scheme)
        self.scheme_account_2 = SchemeAccountFactory(scheme=self.scheme)

        SchemeAccountEntryFactory(user=self.bink_user, scheme_account=self.scheme_account_1)
        SchemeAccountEntryFactory(user=self.other_user, scheme_account=self.scheme_account_2)

        self.payment_card_account_1 = PaymentCardAccountFactory()
        self.payment_card_account_2 = PaymentCardAccountFactory()

        PaymentCardAccountEntryFactory(user=self.bink_user, payment_card_account=self.payment_card_account_1)
        PaymentCardAccountEntryFactory(user=self.other_user, payment_card_account=self.payment_card_account_2)

        internal_service_token = GenerateJWToken(
            self.internal_service_client.organisation.name,
            self.internal_service_client.secret,
            self.internal_service_bundle.bundle_id,
            self.internal_service_id
        ).get_token()
        self.internal_service_auth_headers = {'HTTP_AUTHORIZATION': 'Bearer {}'.format(internal_service_token)}

        token = GenerateJWToken(
            self.other_client.organisation.name,
            self.other_client.secret,
            self.other_bundle.bundle_id,
            other_external_id
        ).get_token()
        self.auth_headers = {'HTTP_AUTHORIZATION': 'Bearer {}'.format(token)}

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    def test_get_single_membership_card(self, mock_get_midas_balance):
        mock_get_midas_balance.return_value = self.scheme_account_1.balances
        resp = self.client.get(
            reverse('membership-card', args=[self.scheme_account_1.id]), **self.internal_service_auth_headers
        )
        self.assertEqual(resp.status_code, 200)

        self.assertTrue(mock_get_midas_balance.delay.called)

        mock_get_midas_balance.return_value = self.scheme_account_2.balances
        resp = self.client.get(
            reverse('membership-card', args=[self.scheme_account_2.id]), **self.internal_service_auth_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(
            reverse('membership-card', args=[self.scheme_account_1.id]), **self.auth_headers
        )
        self.assertEqual(resp.status_code, 404)

        mock_get_midas_balance.return_value = self.scheme_account_2.balances
        resp = self.client.get(reverse('membership-card', args=[self.scheme_account_2.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

    def test_service_get_any_payment_card_account(self):
        resp = self.client.get(
            reverse('payment-card', args=[self.payment_card_account_1.id]), **self.internal_service_auth_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(
            reverse('payment-card', args=[self.payment_card_account_2.id]), **self.internal_service_auth_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(
            reverse('payment-card', args=[self.payment_card_account_1.id]), **self.auth_headers
        )
        self.assertEqual(resp.status_code, 404)

        resp = self.client.get(
            reverse('payment-card', args=[self.payment_card_account_2.id]), **self.auth_headers
        )
        self.assertEqual(resp.status_code, 200)

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    def test_service_get_all_scheme_accounts(self, mock_get_midas_balance):
        mock_get_midas_balance.return_value = self.scheme_account_1.balances
        resp = self.client.get(reverse('membership-cards'), **self.internal_service_auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 2)

        resp = self.client.get(reverse('membership-cards'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

        self.assertTrue(mock_get_midas_balance.delay.called)

    def test_service_get_all_payment_card_accounts(self):
        resp = self.client.get(reverse('payment-cards'), **self.internal_service_auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 2)

        resp = self.client.get(reverse('payment-cards'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_service_token_expiry(self):
        generate_token = GenerateJWToken(
            self.internal_service_client.organisation.name,
            self.internal_service_client.secret,
            self.internal_service_bundle.bundle_id,
            self.internal_service_id
        )
        generate_token.payload['iat'] = time.time() - settings.JWT_EXPIRY_TIME
        expired_token = generate_token.get_token()

        auth_headers = {'HTTP_AUTHORIZATION': 'Bearer {}'.format(expired_token)}

        resp = self.client.get(
            reverse('payment-card', args=[self.payment_card_account_1.id]), **auth_headers
        )
        self.assertEqual(resp.status_code, 401)

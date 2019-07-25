from django.test import TestCase
from hermes.channels import Permit
from user.models import ClientApplicationBundle
from scheme.models import SchemeBundleAssociation, Scheme
from scheme.tests.factories import (SchemeCredentialQuestionFactory, SchemeFactory, SchemeBundleAssociationFactory)
from user.tests.factories import (ClientApplicationBundleFactory, ClientApplicationFactory, OrganisationFactory)
from scheme.models import SchemeBundleAssociation
from user.models import ClientApplicationBundle,  ClientApplication


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

    def test_scheme_query_bink_active_ubiquity_inactive(self):
        bink_permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        ubiquity_permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association,
                                                   SchemeBundleAssociation.INACTIVE)

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

    def test_scheme_query_bink_active_ubiquity_inactive(self):
        bink_permit = self.set_status(self.bink_scheme_bundle_association, SchemeBundleAssociation.ACTIVE)
        ubiquity_permit = self.set_ubiquity_status(self.ubiquity_scheme_bundle_association,
                                                   SchemeBundleAssociation.INACTIVE)

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

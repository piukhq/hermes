import json
from unittest.mock import patch
import httpretty
from django.conf import settings
from payment_card.tests.factories import IssuerFactory, PaymentCardFactory
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from scheme.models import SchemeBundleAssociation, SchemeAccount, JourneyTypes
from payment_card.models import PaymentCardAccount
from scheme.tests.factories import (SchemeAccountFactory, SchemeFactory, SchemeBundleAssociationFactory)
from ubiquity.models import PaymentCardSchemeEntry
from ubiquity.tests.factories import SchemeAccountEntryFactory
from ubiquity.tests.property_token import GenerateJWToken
from user.tests.factories import (ClientApplicationBundleFactory, ClientApplicationFactory, OrganisationFactory,
                                  UserFactory)


class RequestMock:
    channels_permit = None


class ChannelPermitMock:
    def __init__(self, client=None):
        self.client = client


class LinkAnalyst:

    def __init__(self, linked):
        self.count = len(linked)
        self.links_by_membership = {}
        self.links_by_payment = {}
        self.soft_links = []
        self.active_links = []
        for link in linked:
            scheme_account_id = link.scheme_account_id
            if not self.links_by_membership.get(scheme_account_id):
                self.links_by_membership[scheme_account_id] = [link]
            else:
                self.links_by_membership[scheme_account_id].append(link)
            payment_card_account_id = link.payment_card_account_id
            if not self.links_by_payment.get(payment_card_account_id):
                self.links_by_payment[payment_card_account_id] = [link]
            else:
                self.links_by_payment[payment_card_account_id].append(link)
            if link.active_link:
                self.active_links.append(link)
            else:
                self.soft_links.append(link)
        self.count_active_links = len(self.active_links)
        self.count_soft_links = len(self.soft_links)


def set_up_payment_card():

    organisation = OrganisationFactory(name='test_organisation')
    client_app = ClientApplicationFactory(organisation=organisation, name='set up client application',
                                          client_id='2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi')
    bundle = ClientApplicationBundleFactory(bundle_id='test.auth.fake', client=client_app)

    issuer = IssuerFactory(name='Barclays')
    payment_card = PaymentCardFactory(slug='visa', system='visa')

    version_header = {"HTTP_ACCEPT": 'Application/json;v=1.1'}

    payload = {
        "card": {
            "last_four_digits": 5234,
            "currency_code": "GBP",
            "first_six_digits": 423456,
            "name_on_card": "test user 2",
            "token": "H7FdKWKPOPhepzxS4MfUuvTDHxr",
            "fingerprint": "b5fe350d5135ab64a8f3c1097fadefd9effb",
            "year": 22,
            "month": 3,
            "order": 1
        },
        "account": {
            "consents": [
                {
                    "timestamp": 1517549941,
                    "type": 0
                }
            ]
        }
    }
    return client_app, bundle, issuer, payment_card, version_header, payload


def set_up_scheme(bundle):
    scheme = SchemeFactory()
    scheme_bundle_association = SchemeBundleAssociationFactory(scheme=scheme, bundle=bundle,
                                                               status=SchemeBundleAssociation.ACTIVE)
    return scheme, scheme_bundle_association


def set_up_membership_card(user, scheme):
    scheme_account = SchemeAccountFactory(scheme=scheme)
    SchemeAccountEntryFactory(scheme_account=scheme_account, user=user)
    return scheme_account


class TestSoftLinking(APITestCase):
    def _get_auth_token(self, user):
        token = GenerateJWToken(self.client_app.organisation.name, self.client_app.secret, self.bundle.bundle_id,
                                user.external_id).get_token()
        return 'Bearer {}'.format(token)

    def _get_auth_headers(self, user):
        return {'HTTP_AUTHORIZATION': f'{self._get_auth_token(user)}'}

    def _get_service_auth_headers(self):
        return {'HTTP_AUTHORIZATION': f'Token {settings.SERVICE_API_KEY}'}

    @staticmethod
    def failed_midas_callback(request, uri, response_headers):
        return [SchemeAccount.AGENT_NOT_FOUND, response_headers, ""]

    def auto_link_post(self, payload, user):
        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(payload),
                                content_type='application/json', **self._get_auth_headers(user),
                                **self.version_header)
        linked_info = LinkAnalyst(PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id']))
        return resp, linked_info

    def metis_callback(self, card_id=None, status_code=PaymentCardAccount.ACTIVE):
        payload = {
            'status': status_code,
            'id': card_id,

        }
        resp = self.client.put(f'{reverse("update_payment_card_account_status")}', data=json.dumps(payload),
                                content_type='application/json', **self._get_service_auth_headers())
        linked_info = LinkAnalyst(PaymentCardSchemeEntry.objects.filter(payment_card_account_id=card_id))
        return resp, linked_info

    def setUp(self):
        self.client_app, self.bundle, self.issuer, self.payment_card, self.version_header, self.payload = \
            set_up_payment_card()
        external_id = 'test@user.com'
        self.user = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        self.scheme1, self.scheme_bundle_association1 = set_up_scheme(self.bundle)
        self.scheme_account_c1_s1 = set_up_membership_card(self.user, self.scheme1)

        self.scheme2, self.scheme_bundle_association2 = set_up_scheme(self.bundle)
        self.scheme_account_c2_s2 = set_up_membership_card(self.user, self.scheme2)

        self.scheme3, self.scheme_bundle_association3 = set_up_scheme(self.bundle)
        self.scheme_account_c3_s3 = set_up_membership_card(self.user, self.scheme3)

    @httpretty.activate
    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_active_membership_linking_to_payment_card(self, *_):
        # set mcard 2 to pending
        self.scheme_account_c2_s2.status = SchemeAccount.REGISTRATION_FAILED
        self.scheme_account_c2_s2.save()
        resp, linked = self.auto_link_post(self.payload, self.user)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 0)
        # Confirm 3 soft linked cards since payment card is pending
        self.assertEqual(linked.count, 3)
        self.assertEqual(linked.count_soft_links, 3)
        # Now make fail Payment Card with Metis Callback and check none go active
        payment_card_id = resp.data['id']
        resp, linked = self.metis_callback(payment_card_id, status_code=PaymentCardAccount.INVALID_CARD_DETAILS)
        self.assertEqual(linked.count, 3)
        self.assertEqual(linked.count_soft_links, 3)
        # Now make activate Payment Card with Metis Callback
        resp, linked = self.metis_callback(payment_card_id)
        self.assertEqual(resp.status_code, 200)
        # Only 2 active cards should link - soft linked should be self.scheme_account_c2_s2
        self.assertEqual(linked.count_soft_links, 1)
        self.assertEqual(linked.count_active_links, 2)
        self.assertEqual(linked.soft_links[0].scheme_account_id, self.scheme_account_c2_s2.id)
        # todo could add get membership cards and payment cards call here to check status via API
        # Now see if a get balance will activate link
        uri = f'{settings.MIDAS_URL}/{self.scheme2.slug}/balance'
        httpretty.register_uri(
            httpretty.GET,
            uri,
            body=json.dumps({
                "balance": 5
            })
        )
        self.scheme_account_c2_s2.get_midas_balance(JourneyTypes.UPDATE)
        linked = LinkAnalyst(PaymentCardSchemeEntry.objects.filter(payment_card_account_id=payment_card_id))
        self.assertEqual(linked.count_soft_links, 0)
        self.assertEqual(linked.count_active_links, 3)
        # Now see if a get balance fail will convert back to softlink
        httpretty.register_uri(
            httpretty.GET,
            uri,
            body=self.failed_midas_callback
        )
        self.scheme_account_c2_s2.get_midas_balance(JourneyTypes.UPDATE)
        linked = LinkAnalyst(PaymentCardSchemeEntry.objects.filter(payment_card_account_id=payment_card_id))
        self.assertEqual(linked.count_soft_links, 1)
        self.assertEqual(linked.count_active_links, 2)
        self.assertEqual(linked.soft_links[0].scheme_account_id, self.scheme_account_c2_s2.id)


class TestPaymentAutoLink(APITestCase):

    def _get_auth_token(self, user):
        token = GenerateJWToken(self.client_app.organisation.name, self.client_app.secret, self.bundle.bundle_id,
                                user.external_id).get_token()
        return 'Bearer {}'.format(token)

    def _get_auth_headers(self, user):
        return {'HTTP_AUTHORIZATION': f'{self._get_auth_token(user)}'}

    def setUp(self):
        self.client_app, self.bundle, self.issuer, self.payment_card, self.version_header, self.payload = \
            set_up_payment_card()
        self.payload2 = {
            "card": {
                "last_four_digits": 5288,
                "currency_code": "GBP",
                "first_six_digits": 423456,
                "name_on_card": "test user 3",
                "token": "H7FdKWKPOPhepzxS4MfUuvABCDe",
                "fingerprint": "b5fe350d5135ab64a8f3c1097fadefdabcde",
                "year": 23,
                "month": 1,
                "order": 2
            },
            "account": {
                "consents": [
                    {
                        "timestamp": 1517549941,
                        "type": 0
                    }
                ]
            }
        }

        # senario 1 mcards 1 cards 1 mplan

        external_id1 = 'test@user.com'
        self.user1 = UserFactory(external_id=external_id1, client=self.client_app, email=external_id1)

        self.scheme1 = SchemeFactory()
        self.scheme_account_c1_p1 = SchemeAccountFactory(scheme=self.scheme1)
        self.scheme_account_entry1 = SchemeAccountEntryFactory(scheme_account=self.scheme_account_c1_p1,
                                                               user=self.user1)
        self.scheme_bundle_association_p1 = SchemeBundleAssociationFactory(scheme=self.scheme1, bundle=self.bundle,
                                                                           status=SchemeBundleAssociation.ACTIVE)

        # senario 2 mcards 2 cards different mplan

        external_id2 = 'test2@user.com'
        self.user2 = UserFactory(external_id=external_id2, client=self.client_app, email=external_id2)
        self.scheme2 = SchemeFactory()
        self.scheme_account_c1_p2 = SchemeAccountFactory(scheme=self.scheme2)
        self.scheme_account_entry2 = SchemeAccountEntryFactory(scheme_account=self.scheme_account_c1_p2,
                                                               user=self.user2)
        self.scheme_bundle_association_p2 = SchemeBundleAssociationFactory(scheme=self.scheme2, bundle=self.bundle,
                                                                           status=SchemeBundleAssociation.ACTIVE)

        self.scheme3 = SchemeFactory()
        self.scheme_bundle_association_p3 = SchemeBundleAssociationFactory(scheme=self.scheme3, bundle=self.bundle,
                                                                           status=SchemeBundleAssociation.ACTIVE)
        self.scheme_account_c2_p3 = SchemeAccountFactory(scheme=self.scheme3)
        self.scheme_account_entry3 = SchemeAccountEntryFactory(scheme_account=self.scheme_account_c2_p3,
                                                               user=self.user2)

        # senario 3 mcards of same mplan

        external_id3 = 'test3@user.com'
        self.user3 = UserFactory(external_id=external_id3, client=self.client_app, email=external_id3)
        self.scheme4 = SchemeFactory()
        self.scheme_bundle_association_p4 = SchemeBundleAssociationFactory(scheme=self.scheme4, bundle=self.bundle,
                                                                           status=SchemeBundleAssociation.ACTIVE)
        self.scheme_account_c1_p4 = SchemeAccountFactory(scheme=self.scheme4)
        self.scheme_account_entry4 = SchemeAccountEntryFactory(scheme_account=self.scheme_account_c1_p4,
                                                               user=self.user3)
        self.scheme_account_c2_p4 = SchemeAccountFactory(scheme=self.scheme4)
        self.scheme_account_entry4 = SchemeAccountEntryFactory(scheme_account=self.scheme_account_c2_p4,
                                                               user=self.user3)
        self.scheme_account_c3_p4 = SchemeAccountFactory(scheme=self.scheme4)
        self.scheme_account_entry4 = SchemeAccountEntryFactory(scheme_account=self.scheme_account_c3_p4,
                                                               user=self.user3)
        self.scheme_account_c4_p4 = SchemeAccountFactory(scheme=self.scheme4)
        self.scheme_account_entry4 = SchemeAccountEntryFactory(scheme_account=self.scheme_account_c4_p4,
                                                               user=self.user3)

        # senario 4 2 users 4 mcards of same mplan

        external_id4 = 'test4@user.com'
        external_id5 = 'test5@user.com'
        self.user4 = UserFactory(external_id=external_id4, client=self.client_app, email=external_id4)
        self.user5 = UserFactory(external_id=external_id5, client=self.client_app, email=external_id5)
        self.scheme5 = SchemeFactory()
        self.scheme_bundle_association_p4 = SchemeBundleAssociationFactory(scheme=self.scheme5, bundle=self.bundle,
                                                                           status=SchemeBundleAssociation.ACTIVE)

        self.scheme_account_c1_p5_u4 = SchemeAccountFactory(scheme=self.scheme5)
        self.scheme_account_entry_c1_p5_u4 = SchemeAccountEntryFactory(scheme_account=self.scheme_account_c1_p5_u4,
                                                                       user=self.user4)
        self.scheme_account_c2_p5_u4 = SchemeAccountFactory(scheme=self.scheme5)
        self.scheme_account_entry_c2_p5_u4 = SchemeAccountEntryFactory(scheme_account=self.scheme_account_c2_p5_u4,
                                                                       user=self.user4)
        self.scheme_account_c3_p5_u5 = SchemeAccountFactory(scheme=self.scheme5)
        self.scheme_account_entry_c3_p5_u5 = SchemeAccountEntryFactory(scheme_account=self.scheme_account_c3_p5_u5,
                                                                       user=self.user5)
        self.scheme_account_c4_p5_u5 = SchemeAccountFactory(scheme=self.scheme5)
        self.scheme_account_entry_c4_p5_u5 = SchemeAccountEntryFactory(scheme_account=self.scheme_account_c4_p5_u5,
                                                                       user=self.user5)

    def auto_link_post(self, payload, user):
        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(payload),
                                content_type='application/json', **self._get_auth_headers(user),
                                **self.version_header)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        return resp, linked

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_creation_auto_link(self, *_):
        # seanario 1 1 membership cards 1 plans - user 1
        resp, linked = self.auto_link_post(self.payload, self.user1)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 0)
        self.assertEqual(len(linked), 1)

        # Repeat auto link to ensure nothing extra is added and 200 returned
        resp, linked = self.auto_link_post(self.payload, self.user1)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['membership_cards']), 0)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        self.assertEqual(len(linked), 1)

        # Add another membership card
        scheme2 = SchemeFactory()
        SchemeBundleAssociationFactory(scheme=scheme2, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE)
        scheme_account2 = SchemeAccountFactory(scheme=scheme2)
        SchemeAccountEntryFactory(scheme_account=scheme_account2, user=self.user1)

        # Try to add again and see if auto links
        resp, linked = self.auto_link_post(self.payload, self.user1)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['membership_cards']), 0)
        self.assertEqual(len(linked), 2)

        # Make the links active
        for link in linked:
            link.active_link = True
            link.save()

        # Try to add again and see if auto links = True
        resp, linked = self.auto_link_post(self.payload, self.user1)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['membership_cards']), 2)
        self.assertEqual(len(linked), 2)
        for item in resp.data['membership_cards']:
            self.assertEqual(item['active_link'], True)
            self.assertIn('id', item)
            self.assertEqual(len(item), 2)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_auto_link_2_cards_different_plans(self, *_):
        # senario 2 2 membership cards 2 plans - user 2
        resp, linked = self.auto_link_post(self.payload, self.user2)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 0)
        self.assertEqual(len(linked), 2)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_auto_link_4_cards_same_plan(self, *_):
        # senario 3 4 membership cards 1 plans - user 3
        resp, linked = self.auto_link_post(self.payload, self.user3)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 0)
        # Test only card linked to payment card has lowest id
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c1_p4.id)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_auto_link_4cards_2users_same_plan(self, *_):
        # senario 4 4 membership cards 1 plans - user 4
        resp, linked = self.auto_link_post(self.payload, self.user4)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 0)
        # Test only card linked to payment card has lowest id
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c1_p5_u4.id)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_auto_link_4cards_2users_same_plan_other_user_linked(self, *_):
        # senario 4 4 membership cards 1 plans - user 5
        # now with user 5 instead of 4 auto link
        resp, linked = self.auto_link_post(self.payload, self.user5)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 0)
        # Test only card linked to payment card has lowest id in users wallet
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)

        # now repeat user 4 auto link
        resp, linked = self.auto_link_post(self.payload, self.user4)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 0)

        # Now the list should have the card linked in plan above (the other users plan) even though not the oldest
        # Test only card linked to payment card is the card already linked
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_auto_link_2_payment_cards(self, *_):
        # senario 4 4 membership cards 1 plans - user 5 but with an additional linked payment
        # now with user 5 instead of 4 auto link but with payment card 2
        resp, linked = self.auto_link_post(self.payload2, self.user5)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 0)
        # Test only card linked to payment card has lowest id in users wallet
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)

        # now with user 5 instead of 4 auto link as previous test same result as before the auto linking of
        # another payment card should have no effect.

        resp, linked = self.auto_link_post(self.payload, self.user5)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 0)
        # Test only card linked to payment card has lowest id in users wallet
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)

        # now repeat user 4 auto link
        resp, linked = self.auto_link_post(self.payload, self.user4)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 0)

        # Now the list should have the card linked in plan above (the other users plan) even though not the oldest
        # Test only card linked to payment card is the card already linked
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)


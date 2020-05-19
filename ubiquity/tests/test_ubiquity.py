import datetime
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

import arrow
import httpretty
from django.conf import settings
from django.test import RequestFactory, override_settings
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared_config_storage.credentials.encryption import RSACipher, BLAKE2sHash
from shared_config_storage.credentials.utils import AnswerTypeChoices

from hermes.channel_vault import channel_vault
from payment_card.models import PaymentCardAccount
from payment_card.tests.factories import IssuerFactory, PaymentCardAccountFactory, PaymentCardFactory
from scheme.credentials import BARCODE, LAST_NAME, PASSWORD, CARD_NUMBER, USER_NAME, PAYMENT_CARD_HASH
from scheme.models import SchemeBundleAssociation, SchemeAccount, SchemeCredentialQuestion, ThirdPartyConsentLink, \
    JourneyTypes, SchemeAccountCredentialAnswer
from scheme.tests.factories import (SchemeAccountFactory, SchemeBalanceDetailsFactory, SchemeCredentialAnswerFactory,
                                    SchemeCredentialQuestionFactory, SchemeFactory, ConsentFactory,
                                    SchemeBundleAssociationFactory)
from ubiquity.censor_empty_fields import remove_empty
from ubiquity.models import PaymentCardSchemeEntry, PaymentCardAccountEntry, SchemeAccountEntry
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory, ServiceConsentFactory
from ubiquity.tests.property_token import GenerateJWToken
from ubiquity.tests.test_serializers import mock_secrets
from ubiquity.versioning.base.serializers import MembershipTransactionsMixin
from ubiquity.versioning.v1_2.serializers import MembershipCardSerializer, MembershipPlanSerializer, \
    PaymentCardSerializer
from ubiquity.views import MembershipTransactionView, MembershipCardView
from user.tests.factories import (ClientApplicationBundleFactory, ClientApplicationFactory, OrganisationFactory,
                                  UserFactory)


class RequestMock:
    channels_permit = None


class ChannelPermitMock:
    def __init__(self, client=None):
        self.client = client


class MockApiCache:
    key = None
    expire = None
    available_called = None

    def __init__(self, key, expire):
        MockApiCache.key = key
        MockApiCache.data = None
        MockApiCache.expire = expire
        MockApiCache.available_called = False

    @property
    def available(self):
        MockApiCache.available_called = True
        return False

    def save(self, data):
        MockApiCache.data = data


class TestPaymentAutoLink(APITestCase):

    def _get_auth_token(self, user):
        token = GenerateJWToken(self.client_app.organisation.name, self.client_app.secret, self.bundle.bundle_id,
                                user.external_id).get_token()
        return 'Bearer {}'.format(token)

    def _get_auth_headers(self, user):
        return {'HTTP_AUTHORIZATION': f'{self._get_auth_token(user)}'}

    def setUp(self):
        organisation = OrganisationFactory(name='test_organisation')
        self.client_app = ClientApplicationFactory(organisation=organisation, name='set up client application',
                                                   client_id='2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi')
        self.bundle = ClientApplicationBundleFactory(bundle_id='test.auth.fake', client=self.client_app)

        self.issuer = IssuerFactory(name='Barclays')
        self.payment_card = PaymentCardFactory(slug='visa', system='visa')

        self.version_header = {"HTTP_ACCEPT": 'Application/json;v=1.1'}

        self.payload = {
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

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_creation_auto_link(self, *_):
        # seanario 1 1 membership cards 1 plans - user 1

        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(self.payload),
                                content_type='application/json', **self._get_auth_headers(self.user1),
                                **self.version_header)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 1)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        self.assertEqual(len(linked), 1)

        # Repeat auto link to ensure nothing extra is added and 200 returned
        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(self.payload),
                                content_type='application/json', **self._get_auth_headers(self.user1),
                                **self.version_header)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['membership_cards']), 1)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        self.assertEqual(len(linked), 1)

        # Add another membership card
        scheme2 = SchemeFactory()
        SchemeBundleAssociationFactory(scheme=scheme2, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE)
        scheme_account2 = SchemeAccountFactory(scheme=scheme2)
        SchemeAccountEntryFactory(scheme_account=scheme_account2, user=self.user1)

        # Try to add again and see if auto links
        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(self.payload),
                                content_type='application/json', **self._get_auth_headers(self.user1),
                                **self.version_header)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['membership_cards']), 2)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        self.assertEqual(len(linked), 2)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_auto_link_2_cards_different_plans(self, *_):
        # senario 2 2 membership cards 2 plans - user 2
        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(self.payload),
                                content_type='application/json', **self._get_auth_headers(self.user2),
                                **self.version_header)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 2)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        self.assertEqual(len(linked), 2)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_auto_link_4_cards_same_plan(self, *_):
        # senario 3 4 membership cards 1 plans - user 3

        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(self.payload),
                                content_type='application/json', **self._get_auth_headers(self.user3),
                                **self.version_header)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 1)
        # Test first added with lowest id is returned in list
        self.assertEqual(resp.data['membership_cards'][0]['id'], self.scheme_account_c1_p4.id)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        # Test only card linked to payment card has lowest id
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c1_p4.id)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_auto_link_4cards_2users_same_plan(self, *_):
        # senario 4 4 membership cards 1 plans - user 4

        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(self.payload),
                                content_type='application/json', **self._get_auth_headers(self.user4),
                                **self.version_header)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 1)
        # Test first added with lowest id is returned in list
        self.assertEqual(resp.data['membership_cards'][0]['id'], self.scheme_account_c1_p5_u4.id)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        # Test only card linked to payment card has lowest id
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c1_p5_u4.id)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_auto_link_4cards_2users_same_plan_other_user_linked(self, *_):
        # senario 4 4 membership cards 1 plans - user 5
        # now with user 5 instead of 4 auto link
        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(self.payload),
                                content_type='application/json', **self._get_auth_headers(self.user5),
                                **self.version_header)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 1)
        # Test first added with lowest id is returned in list
        self.assertEqual(resp.data['membership_cards'][0]['id'], self.scheme_account_c3_p5_u5.id)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        # Test only card linked to payment card has lowest id in users wallet
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)

        # now repeat user 4 auto link
        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(self.payload),
                                content_type='application/json', **self._get_auth_headers(self.user4),
                                **self.version_header)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 1)

        # Now the list should have the card linked in plan above (the other users plan) even though not the oldest
        self.assertEqual(resp.data['membership_cards'][0]['id'], self.scheme_account_c3_p5_u5.id)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        # Test only card linked to payment card is the card already linked
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_auto_link_2_payment_cards(self, *_):
        # senario 4 4 membership cards 1 plans - user 5 but with an additional linked payment

        # now with user 5 instead of 4 auto link but with payment card 2

        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(self.payload2),
                                content_type='application/json', **self._get_auth_headers(self.user5),
                                **self.version_header)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 1)
        # Test first added with lowest id is returned in list
        self.assertEqual(resp.data['membership_cards'][0]['id'], self.scheme_account_c3_p5_u5.id)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        # Test only card linked to payment card has lowest id in users wallet
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)

        # now with user 5 instead of 4 auto link as previous test same result as before the auto linking of
        # another payment card should have no effect.

        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(self.payload),
                                content_type='application/json', **self._get_auth_headers(self.user5),
                                **self.version_header)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 1)
        # Test first added with lowest id is returned in list
        self.assertEqual(resp.data['membership_cards'][0]['id'], self.scheme_account_c3_p5_u5.id)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        # Test only card linked to payment card has lowest id in users wallet
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)

        # now repeat user 4 auto link
        resp = self.client.post(f'{reverse("payment-cards")}?autoLink=True', data=json.dumps(self.payload),
                                content_type='application/json', **self._get_auth_headers(self.user4),
                                **self.version_header)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data['membership_cards']), 1)

        # Now the list should have the card linked in plan above (the other users plan) even though not the oldest
        self.assertEqual(resp.data['membership_cards'][0]['id'], self.scheme_account_c3_p5_u5.id)
        linked = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=resp.data['id'])
        # Test only card linked to payment card is the card already linked
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].scheme_account.id, self.scheme_account_c3_p5_u5.id)


class TestResources(APITestCase):

    def _get_auth_header(self, user):
        token = GenerateJWToken(self.client_app.organisation.name, self.client_app.secret, self.bundle.bundle_id,
                                user.external_id).get_token()
        return 'Bearer {}'.format(token)

    def setUp(self):
        organisation = OrganisationFactory(name='test_organisation')
        self.client_app = ClientApplicationFactory(organisation=organisation, name='set up client application',
                                                   client_id='2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi')
        self.bundle = ClientApplicationBundleFactory(bundle_id='test.auth.fake', client=self.client_app)
        external_id = 'test@user.com'
        self.user = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        self.scheme = SchemeFactory()
        SchemeBalanceDetailsFactory(scheme_id=self.scheme)

        SchemeCredentialQuestionFactory(scheme=self.scheme, type=BARCODE, label=BARCODE, manual_question=True)
        self.secondary_question = SchemeCredentialQuestionFactory(scheme=self.scheme,
                                                                  type=LAST_NAME,
                                                                  label=LAST_NAME,
                                                                  third_party_identifier=True,
                                                                  options=SchemeCredentialQuestion.LINK_AND_JOIN,
                                                                  auth_field=True,
                                                                  enrol_field=True,
                                                                  register_field=True)
        self.jwp_question = SchemeCredentialQuestionFactory(scheme=self.scheme, type=PAYMENT_CARD_HASH,
                                                            label=PAYMENT_CARD_HASH, enrol_field=True,
                                                            options=SchemeCredentialQuestion.OPTIONAL_JOIN)
        self.scheme_account = SchemeAccountFactory(scheme=self.scheme)
        self.scheme_account_answer = SchemeCredentialAnswerFactory(question=self.scheme.manual_question,
                                                                   scheme_account=self.scheme_account)
        self.second_scheme_account_answer = SchemeCredentialAnswerFactory(question=self.secondary_question,
                                                                          scheme_account=self.scheme_account)
        self.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=self.scheme_account, user=self.user)

        # Need to add an active association since it was assumed no setting was enabled
        self.scheme_bundle_association = SchemeBundleAssociationFactory(scheme=self.scheme, bundle=self.bundle,
                                                                        status=SchemeBundleAssociation.ACTIVE)

        self.scheme_account.update_barcode_and_card_number()

        self.issuer = IssuerFactory(name='Barclays')
        self.payment_card = PaymentCardFactory(slug='visa', system='visa')
        self.payment_card_account = PaymentCardAccountFactory(issuer=self.issuer, payment_card=self.payment_card)
        self.payment_card_account_entry = PaymentCardAccountEntryFactory(user=self.user,
                                                                         payment_card_account=self.payment_card_account)

        self.auth_headers = {'HTTP_AUTHORIZATION': '{}'.format(self._get_auth_header(self.user))}
        self.version_header = {"HTTP_ACCEPT": 'Application/json;v=1.1'}

        self.put_scheme = SchemeFactory()
        SchemeBalanceDetailsFactory(scheme_id=self.put_scheme)

        self.scheme_bundle_association_put = SchemeBundleAssociationFactory(scheme=self.put_scheme,
                                                                            bundle=self.bundle,
                                                                            status=SchemeBundleAssociation.ACTIVE)
        self.put_scheme_manual_q = SchemeCredentialQuestionFactory(scheme=self.put_scheme, type=CARD_NUMBER,
                                                                   label=CARD_NUMBER, manual_question=True)
        self.put_scheme_scan_q = SchemeCredentialQuestionFactory(scheme=self.put_scheme, type=BARCODE,
                                                                 label=BARCODE, scan_question=True)
        self.put_scheme_auth_q = SchemeCredentialQuestionFactory(scheme=self.put_scheme, type=PASSWORD,
                                                                 label=PASSWORD, auth_field=True)

    def test_get_single_payment_card(self):
        payment_card_account = self.payment_card_account_entry.payment_card_account
        expected_result = remove_empty(PaymentCardSerializer(payment_card_account).data)
        resp = self.client.get(reverse('payment-card', args=[payment_card_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    def test_update_payment_card(self):
        payment_card_account = self.payment_card_account_entry.payment_card_account
        new_data = {
            "card": {
                "name_on_card": "new name on card"
            }
        }
        resp = self.client.patch(reverse('payment-card', args=[payment_card_account.id]), data=json.dumps(new_data),
                                 content_type='application/json', **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['card']['name_on_card'], new_data['card']['name_on_card'])

        new_consent = {
            "account": {
                "consents": [
                    {
                        "timestamp": 23947329497,
                        "type": 0
                    }
                ]
            }
        }
        resp = self.client.patch(reverse('payment-card', args=[payment_card_account.id]), data=json.dumps(new_consent),
                                 content_type='application/json', **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['account']['consents'], new_consent['account']['consents'])

    def test_get_all_payment_cards(self):
        PaymentCardAccountEntryFactory(user=self.user)
        payment_card_accounts = PaymentCardAccount.objects.filter(user_set__id=self.user.id).all()
        expected_result = remove_empty(PaymentCardSerializer(payment_card_accounts, many=True).data)
        resp = self.client.get(reverse('payment-cards'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_get_single_membership_card(self, mock_get_midas_balance, *_):
        mock_get_midas_balance.return_value = self.scheme_account.balances
        resp = self.client.get(reverse('membership-card', args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

        self.scheme.test_scheme = True
        self.scheme.save()
        resp = self.client.get(reverse('membership-card', args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 404)

        self.user.is_tester = True
        self.user.save()
        resp = self.client.get(reverse('membership-card', args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

        self.user.is_tester = False
        self.user.save()
        self.scheme.test_scheme = False
        self.scheme.save()

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_get_all_membership_cards(self, *_):
        scheme_account_2 = SchemeAccountFactory(balances=self.scheme_account.balances)
        SchemeBundleAssociationFactory(scheme=scheme_account_2.scheme, bundle=self.bundle,
                                       status=SchemeBundleAssociation.ACTIVE)
        SchemeAccountEntryFactory(scheme_account=scheme_account_2, user=self.user)
        scheme_accounts = SchemeAccount.objects.filter(user_set__id=self.user.id).all()
        expected_result = remove_empty(MembershipCardSerializer(scheme_accounts, many=True).data)
        resp = self.client.get(reverse('membership-cards'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result[0]['account'], resp.json()[0]['account'])
        self.assertEqual(len(resp.json()), 2)

        self.scheme.test_scheme = True
        self.scheme.save()
        resp = self.client.get(reverse('membership-cards'), **self.auth_headers)
        self.assertEqual(len(resp.json()), 1)

        self.user.is_tester = True
        self.user.save()
        resp = self.client.get(reverse('membership-cards'), **self.auth_headers)
        self.assertEqual(len(resp.json()), 2)

        self.user.is_tester = False
        self.user.save()
        self.scheme.test_scheme = False
        self.scheme.save()

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_list_membership_cards_hides_join_cards(self, *_):
        join_scheme_account = SchemeAccountFactory(status=SchemeAccount.JOIN)
        SchemeBundleAssociationFactory(scheme=join_scheme_account.scheme, bundle=self.bundle,
                                       status=SchemeBundleAssociation.ACTIVE)
        SchemeAccountEntryFactory(scheme_account=join_scheme_account, user=self.user)
        scheme_accounts = SchemeAccount.objects.filter(user_set__id=self.user.id, status=SchemeAccount.JOIN).all()
        join_ids = [account.id for account in scheme_accounts]

        resp = self.client.get(reverse('membership-cards'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        resp_join_ids = [card['id'] for card in resp.json()]
        for join_id in join_ids:
            self.assertFalse(join_id in resp_join_ids)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_creation(self, *_):
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
        resp = self.client.post(reverse('payment-cards'), data=json.dumps(payload),
                                content_type='application/json', **self.auth_headers, **self.version_header)
        self.assertEqual(resp.status_code, 201)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_creation_with_id_fails_when_not_internal_user(self, *_):
        payload = {
            "card": {
                "last_four_digits": 5234,
                "currency_code": "GBP",
                "first_six_digits": 423456,
                "name_on_card": "test user 2",
                "token": "H7FdKWKPOPhepzxS4MfUuvTDHxz",
                "fingerprint": "b5fe350d5135ab64a8f3c1097fadefd9effz",
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
        provided_id = 150000000

        resp = self.client.post(reverse('payment-cards'), data=json.dumps(payload),
                                content_type='application/json', HTTP_X_OBJECT_ID=provided_id,
                                **self.auth_headers, **self.version_header)
        self.assertEqual(resp.status_code, 201)
        self.assertNotEqual(resp.json()['id'], provided_id)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    def test_payment_card_replace(self, *_):
        pca = PaymentCardAccountFactory(token='original-token')
        PaymentCardAccountEntryFactory(user=self.user, payment_card_account=pca)
        correct_payload = {
            "card": {
                "last_four_digits": "5234",
                "currency_code": "GBP",
                "first_six_digits": "423456",
                "name_on_card": "test user 2",
                "token": "token-to-ignore",
                "fingerprint": str(pca.fingerprint),
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
        resp = self.client.put(reverse('payment-card', args=[pca.id]), data=json.dumps(correct_payload),
                               content_type='application/json', **self.auth_headers, **self.version_header)
        pca.refresh_from_db()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(pca.token, 'original-token')
        self.assertEqual(pca.pan_end, correct_payload['card']['last_four_digits'])

        wrong_payload = {
            "card": {
                "last_four_digits": "5234",
                "currency_code": "GBP",
                "first_six_digits": "423456",
                "name_on_card": "test user 2",
                "token": "token-to-ignore",
                "fingerprint": "this-is-not-{}".format(pca.fingerprint),
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
        resp = self.client.put(reverse('payment-card', args=[pca.id]), data=json.dumps(wrong_payload),
                               content_type='application/json', **self.auth_headers, **self.version_header)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['detail'], 'cannot override fingerprint.')

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch('ubiquity.views.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_membership_card_status_mapping_active(self, *_):
        test_membership_card = SchemeAccountFactory(status=SchemeAccount.ACTIVE)
        data = MembershipCardSerializer(test_membership_card).data
        self.assertEqual(data['status']['state'], 'authorised')
        self.assertEqual(data['status']['reason_codes'], ['X300'])

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch('ubiquity.views.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_membership_card_status_mapping_user_error(self, *_):
        user_error = SchemeAccount.INVALID_CREDENTIALS
        test_membership_card = SchemeAccountFactory(status=user_error, balances={})
        data = MembershipCardSerializer(test_membership_card).data
        self.assertEqual(data['status']['state'], 'failed')
        self.assertEqual(data['status']['reason_codes'], ['X303'])

        test_membership_card.balances = [{'points': 1.1}]
        test_membership_card.save()
        test_membership_card.refresh_from_db()

        data = MembershipCardSerializer(test_membership_card).data
        self.assertEqual(data['status']['state'], 'failed')
        self.assertEqual(data['status']['reason_codes'], ['X303'])

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch('ubiquity.views.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_membership_card_status_mapping_system_error(self, *_):
        user_error = SchemeAccount.END_SITE_DOWN
        test_membership_card = SchemeAccountFactory(status=user_error, balances={})
        data = MembershipCardSerializer(test_membership_card).data
        self.assertEqual(data['status']['state'], 'pending')
        self.assertEqual(data['status']['reason_codes'], ['X100'])

        test_membership_card.balances = [{'points': 1.1}]
        test_membership_card.save()
        test_membership_card.refresh_from_db()

        data = MembershipCardSerializer(test_membership_card).data
        self.assertEqual(data['status']['state'], 'authorised')
        self.assertEqual(data['status']['reason_codes'], ['X300'])

    @patch('analytics.api.update_scheme_account_attribute')
    @patch('ubiquity.influx_audit.InfluxDBClient')
    @patch('analytics.api.post_event')
    @patch('analytics.api.update_scheme_account_attribute')
    @patch('analytics.api._send_to_mnemosyne')
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch('analytics.api._get_today_datetime')
    def test_membership_card_creation(self, mock_date, mock_hades, mock_async_balance, mock_async_link, *_):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": "3038401022657083"
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": "last_name",
                            "value": "Test"
                        }
                    ]
                }
        }
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                **self.auth_headers)
        self.assertEqual(resp.status_code, 201)
        create_data = resp.data
        # replay and check same data with 200 response
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertDictEqual(resp.data, create_data)
        self.assertTrue(mock_hades.called)
        self.assertTrue(mock_async_link.delay.called)
        self.assertFalse(mock_async_balance.delay.called)

    def test_membership_card_creation_consents(self):
        factory = RequestFactory()
        consent_label = "Test Consent"
        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": "3038401022657083"
                        }
                    ],
                    "enrol_fields": [
                        {
                            "column": "last_name",
                            "value": "Test"
                        },
                        {
                            "column": consent_label,
                            "value": "true"
                        }
                    ]
                }
        }
        request = factory.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                               **self.auth_headers)

        user = MagicMock()
        user.client = self.client_app
        request.user = user
        request.channels_permit = ChannelPermitMock(self.client_app)
        view = MembershipCardView()
        view.request = request

        consent = ConsentFactory.create(scheme=self.scheme)

        ThirdPartyConsentLink.objects.create(consent_label=consent_label,
                                             client_app=self.client_app,
                                             scheme=self.scheme,
                                             consent=consent,
                                             add_field=False,
                                             auth_field=False,
                                             register_field=True,
                                             enrol_field=True)

        consents = view._extract_consent_data(scheme=self.scheme, field='enrol_fields', data=payload)

        self.assertEqual(
            payload['account']['enrol_fields'],
            [{
                "column": "last_name",
                "value": "Test"
            }]
        )
        self.assertEqual(consents, {'consents': [{'id': consent.id, 'value': 'true'}]})

    @patch('analytics.api.update_scheme_account_attribute')
    @patch('ubiquity.influx_audit.InfluxDBClient')
    @patch('analytics.api.post_event')
    @patch('analytics.api.update_scheme_account_attribute')
    @patch('analytics.api._send_to_mnemosyne')
    @patch('ubiquity.views.async_join', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch('analytics.api._get_today_datetime')
    @patch('payment_card.payment.get_secret_key', autospec=True)
    def test_membership_card_jwp_fails_with_bad_payment_card(self, mock_get_hash_secret, *_):
        mock_get_hash_secret.return_value = "testsecret"
        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "enrol_fields": [
                    {
                        "column": LAST_NAME,
                        "value": "last name"
                    },
                    {
                        "column": PAYMENT_CARD_HASH,
                        "value": "nonexistenthash"
                    }
                ]
            }
        }
        resp = self.client.post(reverse("membership-cards"), data=json.dumps(payload), content_type="application/json",
                                **self.auth_headers)

        self.assertTrue(mock_get_hash_secret.called)
        self.assertEqual(resp.status_code, 400)
        error_message = resp.json()["detail"]
        self.assertEqual(error_message, "Provided payment card could not be found or is not related to this user")

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch('ubiquity.views.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_membership_card_update(self, *_):
        payload = json.dumps({
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": "3038401022657083"
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": "last_name",
                            "value": "Test"
                        }
                    ]
                }
        })
        response = self.client.patch(reverse('membership-card', args=[self.scheme_account.id]),
                                     content_type='application/json', data=payload, **self.auth_headers)
        self.assertEqual(response.status_code, 200)

        self.scheme.test_scheme = True
        self.scheme.save()
        response = self.client.patch(reverse('membership-card', args=[self.scheme_account.id]),
                                     content_type='application/json', data=payload, **self.auth_headers)
        self.assertEqual(response.status_code, 404)

        self.user.is_tester = True
        self.user.save()
        response = self.client.patch(reverse('membership-card', args=[self.scheme_account.id]),
                                     content_type='application/json', data=payload, **self.auth_headers)
        self.assertEqual(response.status_code, 200)

        self.scheme.test_scheme = False
        self.scheme.save()
        self.user.is_tester = False
        self.user.save()

    @patch('analytics.api.update_scheme_account_attribute')
    @patch('ubiquity.influx_audit.InfluxDBClient')
    @patch('analytics.api.post_event')
    @patch('analytics.api.update_scheme_account_attribute')
    @patch('analytics.api._send_to_mnemosyne')
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch('analytics.api._get_today_datetime')
    def test_membership_card_delete(self, mock_date, *_):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": "3038401022657083"
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": "last_name",
                            "value": "Test"
                        }
                    ]
                }
        }
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                **self.auth_headers)
        self.assertEqual(resp.status_code, 201)
        create_data = resp.data
        # replay and check same data with 200 response
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertDictEqual(resp.data, create_data)
        account_id = resp.data['id']

        resp_del = self.client.delete(reverse('membership-card', args=[account_id]), data="{}",
                                      content_type='application/json', **self.auth_headers)
        self.assertEqual(resp_del.status_code, 200)
        resp2 = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                 **self.auth_headers)
        self.assertEqual(resp2.status_code, 201)

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_cards_linking(self, *_):
        payment_card_account = self.payment_card_account_entry.payment_card_account
        scheme_account_2 = SchemeAccountFactory(scheme=self.scheme)
        SchemeAccountEntryFactory(user=self.user, scheme_account=scheme_account_2)
        PaymentCardSchemeEntry.objects.create(payment_card_account=payment_card_account,
                                              scheme_account=self.scheme_account)
        params = [
            payment_card_account.id,
            scheme_account_2.id
        ]
        resp = self.client.patch(reverse('membership-link', args=params), **self.auth_headers)
        self.assertEqual(resp.status_code, 201)

        links_data = PaymentCardSerializer(payment_card_account).data['membership_cards']
        for link in links_data:
            if link['id'] == self.scheme_account.id:
                self.assertEqual(link['active_link'], False)
            elif link['id'] == scheme_account_2.id:
                self.assertEqual(link['active_link'], True)

    def test_membership_card_delete_does_not_delete_link_for_cards_shared_between_users(self):

        external_id = 'test2@user.com'
        user_2 = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        SchemeAccountEntryFactory(user=user_2, scheme_account=self.scheme_account)
        PaymentCardAccountEntryFactory(user=user_2,
                                       payment_card_account=self.payment_card_account)

        entry = PaymentCardSchemeEntry.objects.create(payment_card_account=self.payment_card_account,
                                                      scheme_account=self.scheme_account)

        resp = self.client.delete(reverse('membership-card', args=[self.scheme_account.id]),
                                  data="{}",
                                  content_type='application/json', **self.auth_headers)

        self.assertEqual(resp.status_code, 200)

        link = PaymentCardSchemeEntry.objects.filter(pk=entry.pk)
        self.assertEqual(len(link), 1)

    def test_membership_card_delete_removes_link_for_cards_not_shared_between_users(self):

        entry = PaymentCardSchemeEntry.objects.create(payment_card_account=self.payment_card_account,
                                                      scheme_account=self.scheme_account)

        resp = self.client.delete(reverse('membership-card', args=[self.scheme_account.id]),
                                  data="{}",
                                  content_type='application/json', **self.auth_headers)

        self.assertEqual(resp.status_code, 200)

        link = PaymentCardSchemeEntry.objects.filter(pk=entry.pk)
        self.assertEqual(len(link), 0)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                       CELERY_TASK_ALWAYS_EAGER=True,
                       BROKER_BACKEND='memory')
    def test_payment_card_delete_does_not_delete_link_for_cards_shared_between_users(self):
        external_id = 'test2@user.com'
        user_2 = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        SchemeAccountEntryFactory(user=user_2, scheme_account=self.scheme_account)
        PaymentCardAccountEntryFactory(user=user_2,
                                       payment_card_account=self.payment_card_account)

        entry = PaymentCardSchemeEntry.objects.create(payment_card_account=self.payment_card_account,
                                                      scheme_account=self.scheme_account)

        resp = self.client.delete(reverse('payment-card', args=[self.payment_card_account.id]),
                                  data="{}",
                                  content_type='application/json', **self.auth_headers)

        self.assertEqual(resp.status_code, 200)

        link = PaymentCardSchemeEntry.objects.filter(pk=entry.pk)
        self.assertEqual(len(link), 1)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                       CELERY_TASK_ALWAYS_EAGER=True,
                       BROKER_BACKEND='memory')
    @patch('payment_card.metis.metis_request', autospec=True)
    def test_payment_card_delete_removes_link_for_cards_not_shared_between_users(self, mock_metis):
        entry = PaymentCardSchemeEntry.objects.create(payment_card_account=self.payment_card_account,
                                                      scheme_account=self.scheme_account)

        resp = self.client.delete(reverse('payment-card', args=[self.payment_card_account.id]),
                                  data="{}",
                                  content_type='application/json', **self.auth_headers)

        self.assertTrue(mock_metis.called)
        self.assertEqual(resp.status_code, 200)

        link = PaymentCardSchemeEntry.objects.filter(pk=entry.pk)
        self.assertEqual(len(link), 0)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                       CELERY_TASK_ALWAYS_EAGER=True,
                       BROKER_BACKEND='memory')
    @patch('payment_card.metis.metis_request', autospec=True)
    def test_payment_card_delete_by_id(self, _):
        pca = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=self.user, payment_card_account=pca)
        resp = self.client.delete(reverse('payment-card-id', args=[pca.id]), **self.auth_headers)
        pca.refresh_from_db()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(pca.is_deleted)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                       CELERY_TASK_ALWAYS_EAGER=True,
                       BROKER_BACKEND='memory')
    @patch('payment_card.metis.metis_request', autospec=True)
    @patch('ubiquity.views.get_secret_key')
    def test_payment_card_delete_by_hash(self, hash_secret, _):
        hash_secret.return_value = 'test-secret'
        pca = PaymentCardAccountFactory(hash=BLAKE2sHash().new(obj='testhash', key='test-secret'))
        PaymentCardAccountEntry.objects.create(user=self.user, payment_card_account_id=pca.id)
        resp = self.client.delete(reverse('payment-card-hash', args=['testhash']), **self.auth_headers)
        pca.refresh_from_db()

        self.assertTrue(hash_secret.called)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(pca.is_deleted)

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_card_rule_filtering(self, *_):
        resp_payment = self.client.get(reverse('payment-card', args=[self.payment_card_account.id]),
                                       **self.auth_headers)
        resp_membership = self.client.get(reverse('membership-card', args=[self.scheme_account.id]),
                                          **self.auth_headers)
        self.assertEqual(resp_payment.status_code, 200)
        self.assertEqual(resp_membership.status_code, 200)

        self.bundle.issuer.add(IssuerFactory())
        self.scheme_bundle_association.status = SchemeBundleAssociation.INACTIVE
        self.scheme_bundle_association.save()

        resp_payment = self.client.get(reverse('payment-card', args=[self.payment_card_account.id]),
                                       **self.auth_headers)
        resp_membership = self.client.get(reverse('membership-card', args=[self.scheme_account.id]),
                                          **self.auth_headers)
        self.assertEqual(resp_payment.status_code, 404)
        self.assertEqual(resp_membership.status_code, 404)

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_card_rule_filtering_suspended(self, *_):
        """
        This test may need revision when ubiquity suspended feature is implemented
        """
        resp_payment = self.client.get(reverse('payment-card', args=[self.payment_card_account.id]),
                                       **self.auth_headers)
        resp_membership = self.client.get(reverse('membership-card', args=[self.scheme_account.id]),
                                          **self.auth_headers)
        self.assertEqual(resp_payment.status_code, 200)
        self.assertEqual(resp_membership.status_code, 200)

        self.bundle.issuer.add(IssuerFactory())
        self.scheme_bundle_association.status = SchemeBundleAssociation.SUSPENDED
        self.scheme_bundle_association.save()

        resp_payment = self.client.get(reverse('payment-card', args=[self.payment_card_account.id]),
                                       **self.auth_headers)
        resp_membership = self.client.get(reverse('membership-card', args=[self.scheme_account.id]),
                                          **self.auth_headers)
        self.assertEqual(resp_payment.status_code, 404)
        self.assertEqual(resp_membership.status_code, 404)

    @patch('analytics.api')
    @patch('payment_card.metis.enrol_new_payment_card')
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    def test_card_creation_filter(self, *_):
        self.bundle.issuer.add(IssuerFactory())
        self.scheme_bundle_association.status = SchemeBundleAssociation.INACTIVE
        self.scheme_bundle_association.save()
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

        resp = self.client.post(reverse('payment-cards'), data=json.dumps(payload),
                                content_type='application/json', **self.auth_headers, **self.version_header)
        self.assertIn('issuer not allowed', resp.json()['detail'])

        payload = {
            "membership_plan": self.scheme.id,
            "account": {
                "add_fields": [
                    {
                        "column": "barcode",
                        "value": "3038401022657083"
                    }
                ]
            }
        }
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                **self.auth_headers, accept='Application/json;v=1.1')
        self.assertIn('membership plan not allowed', resp.json()['detail'])

    @httpretty.activate
    def test_membership_transactions(self):
        uri = '{}/transactions/scheme_account/{}'.format(settings.HADES_URL, self.scheme_account.id)
        transactions = json.dumps([
            {
                'id': 1,
                'scheme_account_id': self.scheme_account.id,
                'created': arrow.utcnow().format(),
                'date': arrow.utcnow().format(),
                'description': 'Test Transaction',
                'location': 'Bink',
                'points': 200,
                'value': 'A lot',
                'hash': 'ewfnwoenfwen'
            }
        ])
        httpretty.register_uri(httpretty.GET, uri, transactions)
        resp = self.client.get(reverse('membership-card-transactions', args=[self.scheme_account.id]),
                               **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(httpretty.has_request())

        uri = '{}/transactions/user/{}'.format(settings.HADES_URL, self.user.id)
        httpretty.register_uri(httpretty.GET, uri, transactions)
        resp = self.client.get(reverse('membership-card-transactions', args=[self.scheme_account.id]),
                               **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]['amounts'][0]['value'], 200)
        self.assertTrue(httpretty.has_request())

        uri = '{}/transactions/1'.format(settings.HADES_URL)
        transaction = json.dumps({
            'id': 1,
            'scheme_account_id': self.scheme_account.id,
            'created': arrow.utcnow().format(),
            'date': arrow.utcnow().format(),
            'description': 'Test Transaction',
            'location': 'Bink',
            'points': 200,
            'value': 'A lot',
            'hash': 'ewfnwoenfwen'
        })
        httpretty.register_uri(httpretty.GET, uri, transaction)
        resp = self.client.get(reverse('membership-card-transactions', args=[self.scheme_account.id]),
                               **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(httpretty.has_request())

    @patch('scheme.mixins.analytics', autospec=True)
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch('ubiquity.views.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_membership_card_put_missing_membership_plan_error(self, *_):
        sa = SchemeAccountFactory(scheme=self.scheme)
        SchemeAccountEntryFactory(scheme_account=sa, user=self.user)
        payload_put = {
            "account": {
                "add_fields": [
                    {
                        "column": "barcode",
                        "value": "1234401022699099"
                    }
                ],
                "authorise_fields": [
                    {
                        "column": "last_name",
                        "value": "Test Composite"
                    }
                ]
            }
        }
        resp = self.client.put(reverse('membership-card', args=[sa.id]), data=json.dumps(payload_put),
                               content_type='application/json', **self.auth_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json(), {'detail': 'required field membership_plan is missing'})

    @patch('scheme.mixins.analytics', autospec=True)
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch('ubiquity.views.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_membership_card_put_manual_question(self, *_):
        scheme_account = SchemeAccountFactory(scheme=self.put_scheme)
        SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)
        SchemeCredentialAnswerFactory(question=self.put_scheme_manual_q, scheme_account=scheme_account, answer='55555')
        SchemeCredentialAnswerFactory(question=self.put_scheme_auth_q, scheme_account=scheme_account, answer='pass')

        payload = {
            "membership_plan": self.put_scheme.id,
            "account": {
                "add_fields": [
                    {
                        "column": "card_number",
                        "value": "12345"
                    }
                ],
                "authorise_fields": [
                    {
                        "column": "password",
                        "value": "pass"
                    }
                ]
            }
        }

        resp_put = self.client.put(reverse('membership-card', args=[scheme_account.id]), data=json.dumps(payload),
                                   content_type='application/json', **self.auth_headers)

        self.assertEqual(resp_put.status_code, 200)
        scheme_account.refresh_from_db()
        self.assertEqual(scheme_account.status, SchemeAccount.PENDING)
        answers = scheme_account._collect_credentials()
        new_manual_answer = answers.get(self.put_scheme_manual_q.type)
        self.assertEqual(new_manual_answer, "12345")
        self.assertIsNone(answers.get(self.put_scheme_scan_q.type))

    @patch('scheme.mixins.analytics', autospec=True)
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch('ubiquity.views.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_membership_card_put_scan_question(self, *_):
        scheme_account = SchemeAccountFactory(scheme=self.put_scheme)
        SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)
        SchemeCredentialAnswerFactory(question=self.put_scheme_manual_q, scheme_account=scheme_account, answer='55555')
        SchemeCredentialAnswerFactory(question=self.put_scheme_auth_q, scheme_account=scheme_account, answer='pass')

        payload = {
            "membership_plan": self.put_scheme.id,
            "account": {
                "add_fields": [
                    {
                        "column": "barcode",
                        "value": "67890"
                    }
                ],
                "authorise_fields": [
                    {
                        "column": "password",
                        "value": "pass"
                    }
                ]
            }
        }

        resp_put = self.client.put(reverse('membership-card', args=[scheme_account.id]), data=json.dumps(payload),
                                   content_type='application/json', **self.auth_headers)
        self.assertEqual(resp_put.status_code, 200)
        scheme_account.refresh_from_db()
        self.assertEqual(scheme_account.status, SchemeAccount.PENDING)
        answers = scheme_account._collect_credentials()
        new_scan_answer = answers.get(self.put_scheme_scan_q.type)
        self.assertEqual(new_scan_answer, "67890")
        self.assertIsNone(answers.get(self.put_scheme_manual_q.type))

    @patch('scheme.mixins.analytics', autospec=True)
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch('ubiquity.views.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_membership_card_put_with_previous_balance(self, *_):
        scheme_account = SchemeAccountFactory(scheme=self.put_scheme)
        SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)
        SchemeCredentialAnswerFactory(question=self.put_scheme_manual_q, scheme_account=scheme_account, answer='9999')
        SchemeCredentialAnswerFactory(question=self.put_scheme_auth_q, scheme_account=scheme_account, answer='pass')
        scheme_account.balances = [{"points": 1, "scheme_account_id": 27308}]
        scheme_account.save()

        payload = {
            "membership_plan": self.put_scheme.id,
            "account": {
                "add_fields": [
                    {
                        "column": "card_number",
                        "value": "test12345678"
                    }
                ],
                "authorise_fields": [
                    {
                        "column": "password",
                        "value": "pass"
                    }
                ]
            }
        }

        resp_put = self.client.put(reverse('membership-card', args=[scheme_account.id]), data=json.dumps(payload),
                                   content_type='application/json', **self.auth_headers)

        self.assertEqual(resp_put.status_code, 200)
        scheme_account.refresh_from_db()
        self.assertEqual(scheme_account.status, SchemeAccount.PENDING)
        self.assertFalse(scheme_account.balances)

    @patch('scheme.mixins.analytics', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch('ubiquity.views.async_balance', autospec=True)
    @patch('ubiquity.views.async_registration', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_membership_card_patch(self, *_):
        external_id = 'test patch user 1'
        user = UserFactory(external_id=external_id, client=self.client_app, email=external_id)
        auth_headers = {'HTTP_AUTHORIZATION': '{}'.format(self._get_auth_header(user))}
        sa = SchemeAccountFactory(scheme=self.scheme)
        SchemeAccountEntryFactory(user=user, scheme_account=sa)
        SchemeCredentialAnswerFactory(question=self.scheme.manual_question, scheme_account=sa, answer='12345')
        SchemeCredentialAnswerFactory(question=self.secondary_question, scheme_account=sa, answer='name')
        expected_value = {'last_name': 'changed name'}
        payload_update = {
            "account": {
                "authorise_fields": [
                    {
                        "column": "last_name",
                        "value": "changed name"
                    }
                ]
            }
        }
        resp_update = self.client.patch(reverse('membership-card', args=[sa.id]), data=json.dumps(payload_update),
                                        content_type='application/json', **auth_headers)
        self.assertEqual(resp_update.status_code, 200)
        sa.status = SchemeAccount.PRE_REGISTERED_CARD
        sa.save()
        sa.refresh_from_db()
        self.assertEqual(sa._collect_credentials()['last_name'], expected_value['last_name'])

        payload_register = {
            "account": {
                "registration_fields": [
                    {
                        "column": "last_name",
                        "value": "new changed name"
                    }
                ]
            }
        }
        resp_register = self.client.patch(reverse('membership-card', args=[sa.id]), data=json.dumps(payload_register),
                                          content_type='application/json', **auth_headers)
        self.assertEqual(resp_register.status_code, 200)

    @patch('ubiquity.cache_decorators.ApiCache', new=MockApiCache)
    def test_membership_plans(self):
        MockApiCache.available_called = False
        MockApiCache.expire = 0
        resp = self.client.get(reverse('membership-plans'), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(isinstance(resp.json(), list))
        self.assertTrue(MockApiCache.available_called)
        self.assertEqual(MockApiCache.key, 'm_plans:test.auth.fake:0:1.2')
        self.assertEqual(MockApiCache.expire, 60 * 60 * 24)
        self.assertListEqual(MockApiCache.data, resp.json())

        schemes_number = len(resp.json())

        self.scheme.test_scheme = True
        self.scheme.save()
        resp = self.client.get(reverse('membership-plans'), **self.auth_headers)
        self.assertLess(len(resp.json()), schemes_number)

        self.user.is_tester = True
        self.user.save()
        resp = self.client.get(reverse('membership-plans'), **self.auth_headers)
        self.assertEqual(len(resp.json()), schemes_number)

        self.scheme.test_scheme = False
        self.scheme.save()
        self.user.is_tester = False
        self.user.save()

    @patch('ubiquity.cache_decorators.ApiCache', new=MockApiCache)
    def test_membership_plan(self):
        mock_request_context = MagicMock()
        mock_request_context.user = self.user
        MockApiCache.available_called = False
        MockApiCache.expire = 0
        resp = self.client.get(reverse('membership-plan', args=[self.scheme.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(MockApiCache.available_called)
        self.assertEqual(MockApiCache.key, f'm_plans:{self.scheme.id}:test.auth.fake:0:1.2')
        self.assertEqual(MockApiCache.expire, 60 * 60 * 24)
        self.assertDictEqual(MockApiCache.data, resp.json())

        self.assertEqual(
            remove_empty(MembershipPlanSerializer(self.scheme, context={'request': mock_request_context}).data),
            resp.json()
        )

        self.scheme.test_scheme = True
        self.scheme.save()
        resp = self.client.get(reverse('membership-plan', args=[self.scheme.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 404)

        self.user.is_tester = True
        self.user.save()
        resp = self.client.get(reverse('membership-plan', args=[self.scheme.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)

        self.scheme.test_scheme = False
        self.scheme.save()
        self.user.is_tester = False
        self.user.save()

    def test_composite_membership_plan(self):
        mock_request_context = MagicMock()
        mock_request_context.user = self.user

        expected_result = remove_empty(MembershipPlanSerializer(self.scheme_account.scheme,
                                                                context={'request': mock_request_context}).data)
        resp = self.client.get(reverse('membership-card-plan', args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(expected_result, resp.json())

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_membership_card_balance(self, mock_get_midas_balance, *_):
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'reward_tier': 0,
            'balance': Decimal('20'),
            'is_stale': False
        }
        expected_keys = {'value', 'currency', 'updated_at'}
        self.scheme_account.get_cached_balance()
        resp = self.client.get(reverse('membership-card', args=[self.scheme_account.id]), **self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['balances'][0]['value'], 100)
        self.assertTrue(expected_keys.issubset(set(resp.json()['balances'][0].keys())))

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_get_cached_balance_link(self, mock_get_midas_balance, *_):
        test_scheme_account = SchemeAccountFactory()
        mock_get_midas_balance.return_value = {
            'value': Decimal('10'),
            'points': Decimal('100'),
            'points_label': '100',
            'value_label': "$10",
            'reward_tier': 0,
            'balance': Decimal('20'),
            'is_stale': False
        }

        self.assertFalse(test_scheme_account.balances)
        test_scheme_account.get_cached_balance()
        self.assertTrue(mock_get_midas_balance.called)
        self.assertEqual(mock_get_midas_balance.call_args[1]['journey'], JourneyTypes.LINK)
        self.assertTrue(test_scheme_account.balances)

        test_scheme_account.get_cached_balance()
        self.assertEqual(mock_get_midas_balance.call_args[1]['journey'], JourneyTypes.UPDATE)

    @patch('analytics.api.update_scheme_account_attribute')
    @patch('ubiquity.influx_audit.InfluxDBClient')
    @patch('analytics.api.post_event')
    @patch('analytics.api._send_to_mnemosyne')
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch('analytics.api._get_today_datetime')
    def test_existing_membership_card_creation_fail(self, mock_date, *_):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": self.scheme_account.barcode
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": "last_name",
                            "value": "Test Fail"
                        }
                    ]
                }
        }
        new_external_id = 'Test User 2'
        new_user = UserFactory(external_id=new_external_id, client=self.client_app, email=new_external_id)
        PaymentCardAccountEntryFactory(user=new_user, payment_card_account=self.payment_card_account)
        auth_header = self._get_auth_header(new_user)
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                HTTP_AUTHORIZATION=auth_header)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(
            'This card already exists, but the provided credentials do not match.',
            resp.json().get('detail')
        )

    def test_membership_plan_serializer_method(self):
        serializer = MembershipPlanSerializer()
        test_dict = [
            {'column': 1},
            {'column': 2},
            {'column': 3}
        ]
        expected = [
            {'column': 1, 'alternatives': [2, 3]},
            {'column': 2, 'alternatives': [1, 3]},
            {'column': 3, 'alternatives': [1, 2]}
        ]
        serializer._add_alternatives_key(test_dict)
        self.assertEqual(expected, test_dict)

    @patch('ubiquity.views.async_all_balance.delay')
    def test_get_service(self, mock_async_all_balance):
        ServiceConsentFactory(user=self.user)
        resp = self.client.get(reverse('service'), **self.auth_headers)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_async_all_balance.called)
        self.assertEqual(mock_async_all_balance.call_args[0][0], self.user.id)

    @patch('ubiquity.views.metis', autospec=True)
    def test_delete_service(self, _):
        user = UserFactory(external_id='test@delete.user', client=self.client_app, email='test@delete.user')
        ServiceConsentFactory(user=user)
        pcard_delete = PaymentCardAccountFactory()
        pcard_unlink = PaymentCardAccountFactory()
        mcard_delete = SchemeAccountFactory()
        mcard_unlink = SchemeAccountFactory()
        auth_headers = {'HTTP_AUTHORIZATION': '{}'.format(self._get_auth_header(user))}

        PaymentCardAccountEntry.objects.create(user_id=user.id, payment_card_account_id=pcard_delete.id)
        PaymentCardAccountEntry.objects.create(user_id=user.id, payment_card_account_id=pcard_unlink.id)
        PaymentCardAccountEntry.objects.create(user_id=self.user.id, payment_card_account_id=pcard_unlink.id)

        SchemeAccountEntry.objects.create(user_id=user.id, scheme_account_id=mcard_delete.id)
        SchemeAccountEntry.objects.create(user_id=user.id, scheme_account_id=mcard_unlink.id)
        SchemeAccountEntry.objects.create(user_id=self.user.id, scheme_account_id=mcard_unlink.id)

        response = self.client.delete(reverse('service'), **auth_headers)
        self.assertEqual(response.status_code, 200)

        pcard_unlink.refresh_from_db()
        pcard_delete.refresh_from_db()
        mcard_unlink.refresh_from_db()
        mcard_delete.refresh_from_db()

        self.assertTrue(pcard_delete.is_deleted)
        self.assertTrue(mcard_delete.is_deleted)
        self.assertFalse(pcard_unlink.is_deleted)
        self.assertFalse(mcard_unlink.is_deleted)

        non_deleted_links = SchemeAccountEntry.objects.filter(user_id=user.id).count()
        self.assertEqual(non_deleted_links, 0)

    @patch('scheme.mixins.analytics', autospec=True)
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    def test_auto_link(self, *_):
        external_id = 'test auto link'
        user = UserFactory(external_id=external_id, client=self.client_app, email=external_id)

        auth_header = self._get_auth_header(user)
        auth_headers = {'HTTP_AUTHORIZATION': '{}'.format(auth_header)}
        payment_card_account = PaymentCardAccountFactory(issuer=self.issuer, payment_card=self.payment_card)
        PaymentCardAccountEntryFactory(user=user, payment_card_account=payment_card_account)
        query = {'payment_card_account_id': payment_card_account.id}

        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": "123456789"
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": "last_name",
                            "value": "Test Successful Link"
                        }
                    ]
                }
        }
        success_resp = self.client.post(f'{reverse("membership-cards")}?autoLink=True', data=json.dumps(payload),
                                        content_type='application/json', **auth_headers)

        self.assertEqual(success_resp.status_code, 201)
        query['scheme_account_id'] = success_resp.json()['id']
        self.assertTrue(PaymentCardSchemeEntry.objects.filter(**query).exists())

        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": "barcode",
                            "value": "987654321"
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": "last_name",
                            "value": "Test Excluded Link"
                        }
                    ]
                }
        }
        fail_resp = self.client.post(f'{reverse("membership-cards")}?autoLink=True', data=json.dumps(payload),
                                     content_type='application/json', **auth_headers)

        self.assertEqual(fail_resp.status_code, 201)
        query['scheme_account_id'] = fail_resp.json()['id']
        self.assertFalse(PaymentCardSchemeEntry.objects.filter(**query).exists())

    def test_membership_card_transactions_user_filters(self):
        sae_correct = SchemeAccountEntryFactory(user=self.user)
        sae_wrong = SchemeAccountEntryFactory()
        data = [
            {'scheme_account_id': sae_correct.scheme_account_id},
            {'scheme_account_id': sae_wrong.scheme_account_id},
            {'scheme_account_id': sae_wrong.scheme_account_id},
            {'scheme_account_id': sae_wrong.scheme_account_id},
            {'scheme_account_id': sae_correct.scheme_account_id},
            {'scheme_account_id': sae_wrong.scheme_account_id}
        ]
        filtered_data = MembershipTransactionView._filter_transactions_for_current_user(self.user, data)
        self.assertEqual(len(filtered_data), 2)
        self.assertTrue(MembershipTransactionView._account_belongs_to_user(self.user, sae_correct.scheme_account_id))
        self.assertFalse(MembershipTransactionView._account_belongs_to_user(self.user, sae_wrong.scheme_account_id))


class TestAgainWithWeb2(TestResources):

    def _get_auth_header(self, user):
        token = user.create_token()
        return 'Token {}'.format(token)


class TestMembershipCardCredentials(APITestCase):
    def setUp(self):
        organisation = OrganisationFactory(name='set up authentication for credentials')
        client = ClientApplicationFactory(organisation=organisation, name='set up credentials application')
        self.bundle = ClientApplicationBundleFactory(bundle_id='test.credentials.fake', client=client)
        external_id = 'credentials@user.com'
        self.user = UserFactory(external_id=external_id, client=client, email=external_id)
        self.scheme = SchemeFactory()
        self.scheme_bundle_association = SchemeBundleAssociationFactory(scheme=self.scheme, bundle=self.bundle,
                                                                        status=SchemeBundleAssociation.ACTIVE)
        SchemeBalanceDetailsFactory(scheme_id=self.scheme)
        SchemeCredentialQuestionFactory(scheme=self.scheme, type=BARCODE, label=BARCODE, manual_question=True,
                                        add_field=True)
        SchemeCredentialQuestionFactory(scheme=self.scheme, type=PASSWORD, label=PASSWORD, auth_field=True)
        secondary_question = SchemeCredentialQuestionFactory(scheme=self.scheme,
                                                             type=LAST_NAME,
                                                             label=LAST_NAME,
                                                             third_party_identifier=True,
                                                             options=SchemeCredentialQuestion.LINK,
                                                             auth_field=True)
        self.scheme_account = SchemeAccountFactory(scheme=self.scheme)
        self.scheme_account_answer = SchemeCredentialAnswerFactory(question=self.scheme.manual_question,
                                                                   scheme_account=self.scheme_account)
        self.second_scheme_account_answer = SchemeCredentialAnswerFactory(question=secondary_question,
                                                                          scheme_account=self.scheme_account)
        self.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=self.scheme_account, user=self.user)
        token = GenerateJWToken(client.organisation.name, client.secret, self.bundle.bundle_id, external_id).get_token()
        self.auth_headers = {'HTTP_AUTHORIZATION': 'Bearer {}'.format(token)}

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch('ubiquity.views.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_update_new_and_existing_credentials(self, *_):
        payload = {
            'account': {
                'authorise_fields': [
                    {
                        'column': 'last_name',
                        'value': 'New Last Name'
                    },
                    {
                        'column': 'password',
                        'value': 'newpassword'
                    }
                ]
            }
        }
        resp = self.client.patch(reverse('membership-card', args=[self.scheme_account.id]), data=json.dumps(payload),
                                 content_type='application/json', **self.auth_headers)
        self.assertEqual(resp.status_code, 200)


class TestResourcesV1_2(APITestCase):
    def _get_auth_header(self, user):
        token = GenerateJWToken(self.client_app.organisation.name, self.client_app.secret, self.bundle.bundle_id,
                                user.external_id).get_token()
        return 'Bearer {}'.format(token)

    def setUp(self) -> None:
        self.rsa = RSACipher()
        self.bundle_id = 'com.barclays.test'
        self.pub_key = mock_secrets["bundle_secrets"][self.bundle_id]['public_key']

        organisation = OrganisationFactory(name='test_organisation')
        self.client_app = ClientApplicationFactory(organisation=organisation, name='set up client application',
                                                   client_id='2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi')
        self.bundle = ClientApplicationBundleFactory(bundle_id=self.bundle_id, client=self.client_app)
        self.scheme = SchemeFactory()

        self.question_1 = SchemeCredentialQuestionFactory(
            scheme=self.scheme, answer_type=AnswerTypeChoices.SENSITIVE.value, auth_field=True, type=PASSWORD,
            label=PASSWORD, options=SchemeCredentialQuestion.LINK
        )
        self.question_2 = SchemeCredentialQuestionFactory(
            scheme=self.scheme, answer_type=AnswerTypeChoices.TEXT.value, manual_question=True,
            label=USER_NAME
        )

        external_id = 'test@user.com'
        self.user = UserFactory(external_id=external_id, client=self.client_app, email=external_id)

        # Need to add an active association since it was assumed no setting was enabled
        self.scheme_bundle_association = SchemeBundleAssociationFactory(scheme=self.scheme, bundle=self.bundle,
                                                                        status=SchemeBundleAssociation.ACTIVE)

        self.auth_headers = {'HTTP_AUTHORIZATION': '{}'.format(self._get_auth_header(self.user))}
        self.version_header = {"HTTP_ACCEPT": 'Application/json;v=1.2'}

    @patch.object(channel_vault, 'all_secrets', mock_secrets)
    @patch('analytics.api.update_scheme_account_attribute')
    @patch('ubiquity.influx_audit.InfluxDBClient')
    @patch('analytics.api.post_event')
    @patch('analytics.api.update_scheme_account_attribute')
    @patch('analytics.api._send_to_mnemosyne')
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch('analytics.api._get_today_datetime')
    def test_sensitive_field_decryption(self, mock_date, mock_hades, mock_async_balance, mock_async_link, *_):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        password = 'Password1'
        question_answer2 = 'some other answer'
        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": self.question_2.label,
                            "value": question_answer2,
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": self.question_1.label,
                            "value": self.rsa.encrypt(password, pub_key=self.pub_key),
                        }
                    ]
                }
        }
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                **self.auth_headers, **self.version_header)
        self.assertEqual(resp.status_code, 201)

        scheme_acc = SchemeAccount.objects.get(pk=resp.data['id'])
        answers = SchemeAccountCredentialAnswer.objects.filter(scheme_account=scheme_acc).all()

        self.assertEqual(len(answers), 1)
        self.assertEqual(password, mock_async_link.delay.call_args[0][0][PASSWORD])

        self.assertTrue(mock_hades.called)
        self.assertTrue(mock_async_link.delay.called)
        self.assertFalse(mock_async_balance.delay.called)

    @patch.object(channel_vault, 'all_secrets', mock_secrets)
    @patch('analytics.api.update_scheme_account_attribute')
    @patch('ubiquity.influx_audit.InfluxDBClient')
    @patch('analytics.api.post_event')
    @patch('analytics.api.update_scheme_account_attribute')
    @patch('analytics.api._send_to_mnemosyne')
    @patch('ubiquity.views.async_link', autospec=True)
    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch('analytics.api._get_today_datetime')
    def test_error_raised_when_sensitive_field_is_not_encrypted(self, mock_date, mock_hades, mock_async_balance,
                                                                mock_async_link, *_):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        password = 'Password1'
        question_answer2 = 'some other answer'
        payload = {
            "membership_plan": self.scheme.id,
            "account":
                {
                    "add_fields": [
                        {
                            "column": self.question_2.label,
                            "value": question_answer2,
                        }
                    ],
                    "authorise_fields": [
                        {
                            "column": self.question_1.label,
                            "value": password,
                        }
                    ]
                }
        }
        resp = self.client.post(reverse('membership-cards'), data=json.dumps(payload), content_type='application/json',
                                **self.auth_headers, **self.version_header)
        self.assertEqual(resp.status_code, 400)

        self.assertFalse(mock_hades.called)
        self.assertFalse(mock_async_link.delay.called)
        self.assertFalse(mock_async_balance.delay.called)

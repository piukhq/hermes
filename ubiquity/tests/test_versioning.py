from unittest.mock import patch

from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from scheme.credentials import BARCODE, LAST_NAME
from scheme.models import SchemeBundleAssociation, SchemeCredentialQuestion, SchemeAccount
from scheme.tests.factories import (SchemeAccountFactory, SchemeBalanceDetailsFactory, SchemeCredentialAnswerFactory,
                                    SchemeCredentialQuestionFactory, SchemeFactory, SchemeBundleAssociationFactory,
                                    SchemeImageFactory)
from ubiquity.tests.factories import SchemeAccountEntryFactory
from ubiquity.tests.property_token import GenerateJWToken
from ubiquity.versioning.base.serializers import MembershipTransactionsMixin
from user.tests.factories import (ClientApplicationBundleFactory, ClientApplicationFactory, OrganisationFactory,
                                  UserFactory)


class TestResources(APITestCase):

    @classmethod
    def _get_auth_header(cls, user):
        token = GenerateJWToken(cls.client_app.organisation.name, cls.client_app.secret, cls.bundle.bundle_id,
                                user.external_id).get_token()
        return {'HTTP_AUTHORIZATION': 'Bearer {}'.format(token)}

    @staticmethod
    def _get_version_header(version):
        return {'HTTP_ACCEPT': f"application/vnd.bink+json;v={version}"}

    @classmethod
    def setUpTestData(cls):
        organisation = OrganisationFactory(name='test_version_organisation')
        cls.client_app = ClientApplicationFactory(
            organisation=organisation,
            name='versioning client application',
            client_id='2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi'
        )
        cls.bundle = ClientApplicationBundleFactory(bundle_id='test.version.fake', client=cls.client_app)
        external_id = 'test@user.com'
        cls.user = UserFactory(external_id=external_id, client=cls.client_app, email=external_id)
        cls.scheme = SchemeFactory()
        cls.scheme_image = SchemeImageFactory(scheme=cls.scheme, image_type_code=3)
        SchemeBalanceDetailsFactory(scheme_id=cls.scheme)

        SchemeCredentialQuestionFactory(scheme=cls.scheme, type=BARCODE, label=BARCODE, manual_question=True)
        cls.secondary_question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme,
            type=LAST_NAME,
            label=LAST_NAME,
            third_party_identifier=True,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            auth_field=True,
            enrol_field=True,
            register_field=True
        )
        cls.scheme_account = SchemeAccountFactory(scheme=cls.scheme)
        cls.scheme_account_answer = SchemeCredentialAnswerFactory(
            question=cls.scheme.manual_question,
            scheme_account=cls.scheme_account
        )
        cls.second_scheme_account_answer = SchemeCredentialAnswerFactory(
            question=cls.secondary_question,
            scheme_account=cls.scheme_account
        )
        cls.scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=cls.scheme_account,
            user=cls.user
        )
        cls.scheme_bundle_association = SchemeBundleAssociationFactory(
            scheme=cls.scheme, bundle=cls.bundle,
            status=SchemeBundleAssociation.ACTIVE
        )
        SchemeBalanceDetailsFactory(scheme_id=cls.scheme)
        auth_header = cls._get_auth_header(cls.user)
        cls.headers_v1_1 = {**auth_header, **cls._get_version_header('1.1.4')}
        cls.headers_v1_2 = {**auth_header, **cls._get_version_header('1.2')}
        cls.headers_v1_3 = {**auth_header, **cls._get_version_header('1.3')}
        cls.resp_wrong_ver = {**auth_header, **cls._get_version_header('-3')}
        cls.resp_wrong_format = {**auth_header, 'HTTP_ACCEPT': "application/vnd.bink+jso"}
        cls.headers_no_ver = auth_header

    def _check_versioned_response(self, resp_v1_1, resp_v1_2, resp_v1_3, resp_no_ver, resp_wrong_ver,
                                  resp_wrong_format):
        self.assertEqual(resp_v1_1.get('X-API-Version'), '1.1')
        self.assertEqual(resp_v1_2.get('X-API-Version'), '1.2')
        self.assertEqual(resp_v1_3.get('X-API-Version'), '1.3')
        self.assertEqual(resp_no_ver.get('X-API-Version'), '1.3')
        self.assertEqual(resp_wrong_ver.get('X-API-Version'), '1.3')
        self.assertIsNone(resp_wrong_format.get('X-API-Version'))

    def test_membership_plan_versioning(self):
        resp_v1_1 = self.client.get(reverse('membership-plans'), **self.headers_v1_1)
        resp_v1_2 = self.client.get(reverse('membership-plans'), **self.headers_v1_2)
        resp_v1_3 = self.client.get(reverse('membership-plans'), **self.headers_v1_3)
        resp_no_ver = self.client.get(reverse('membership-plans'), **self.headers_no_ver)
        resp_wrong_ver = self.client.get(reverse('membership-plans'), **self.resp_wrong_ver)
        resp_wrong_format = self.client.get(reverse('membership-plans'), **self.resp_wrong_format)

        self._check_versioned_response(resp_v1_1, resp_v1_2, resp_v1_3, resp_no_ver, resp_wrong_ver, resp_wrong_format)

    def test_membership_plan_versioned_content(self):
        resp_v1_1 = self.client.get(reverse('membership-plan', args=[self.scheme.id]), **self.headers_v1_1)
        resp_v1_2 = self.client.get(reverse('membership-plan', args=[self.scheme.id]), **self.headers_v1_2)

        self.assertNotIn('fees', resp_v1_1.json()['account'])
        self.assertIn('fees', resp_v1_2.json()['account'])
        self.assertNotIn('content', resp_v1_1.json())
        self.assertIn('content', resp_v1_2.json())

    def test_membership_plan_versioned_images(self):
        resp_v1_1 = self.client.get(reverse('membership-plan', args=[self.scheme.id]), **self.headers_v1_1)
        resp_v1_2 = self.client.get(reverse('membership-plan', args=[self.scheme.id]), **self.headers_v1_2)
        resp_v1_3 = self.client.get(reverse('membership-plan', args=[self.scheme.id]), **self.headers_v1_3)

        image_v1_1 = resp_v1_1.json()['images'][0]
        image_v1_2 = resp_v1_2.json()['images'][0]
        image_v1_3 = resp_v1_3.json()['images'][0]

        self.assertNotIn('dark_mode_url', image_v1_1)
        self.assertNotIn('dark_mode_url', image_v1_2)
        self.assertIn('dark_mode_url', image_v1_3)

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_membership_card_versioning(self, *_):
        resp_v1_1 = self.client.get(reverse('membership-cards'), **self.headers_v1_1)
        resp_v1_2 = self.client.get(reverse('membership-cards'), **self.headers_v1_2)
        resp_v1_3 = self.client.get(reverse('membership-cards'), **self.headers_v1_3)
        resp_no_ver = self.client.get(reverse('membership-cards'), **self.headers_no_ver)
        resp_wrong_ver = self.client.get(reverse('membership-cards'), **self.resp_wrong_ver)
        resp_wrong_format = self.client.get(reverse('membership-cards'), **self.resp_wrong_format)

        self._check_versioned_response(resp_v1_1, resp_v1_2, resp_v1_3, resp_no_ver, resp_wrong_ver, resp_wrong_format)

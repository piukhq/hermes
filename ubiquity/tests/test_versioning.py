from unittest.mock import patch

from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from scheme.credentials import BARCODE, LAST_NAME
from scheme.models import SchemeBundleAssociation, SchemeCredentialQuestion, SchemeAccount
from scheme.tests.factories import (SchemeAccountFactory, SchemeBalanceDetailsFactory, SchemeCredentialAnswerFactory,
                                    SchemeCredentialQuestionFactory, SchemeFactory, SchemeBundleAssociationFactory)
from ubiquity.tests.factories import SchemeAccountEntryFactory
from ubiquity.tests.property_token import GenerateJWToken
from ubiquity.versioning.base.serializers import MembershipTransactionsMixin
from user.tests.factories import (ClientApplicationBundleFactory, ClientApplicationFactory, OrganisationFactory,
                                  UserFactory)


class TestResources(APITestCase):

    def _get_auth_header(self, user):
        token = GenerateJWToken(self.client_app.organisation.name, self.client_app.secret, self.bundle.bundle_id,
                                user.external_id).get_token()
        return {'HTTP_AUTHORIZATION': 'Bearer {}'.format(token)}

    @staticmethod
    def _get_version_header(version):
        return {'HTTP_ACCEPT': f"application/vnd.bink+json;v={version}"}

    def setUp(self):
        organisation = OrganisationFactory(name='test_version_organisation')
        self.client_app = ClientApplicationFactory(organisation=organisation, name='versioning client application',
                                                   client_id='2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi')
        self.bundle = ClientApplicationBundleFactory(bundle_id='test.version.fake', client=self.client_app)
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
        self.scheme_account = SchemeAccountFactory(scheme=self.scheme)
        self.scheme_account_answer = SchemeCredentialAnswerFactory(question=self.scheme.manual_question,
                                                                   scheme_account=self.scheme_account)
        self.second_scheme_account_answer = SchemeCredentialAnswerFactory(question=self.secondary_question,
                                                                          scheme_account=self.scheme_account)
        self.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=self.scheme_account, user=self.user)
        self.scheme_bundle_association = SchemeBundleAssociationFactory(scheme=self.scheme, bundle=self.bundle,
                                                                        status=SchemeBundleAssociation.ACTIVE)
        SchemeBalanceDetailsFactory(scheme_id=self.scheme)
        auth_header = self._get_auth_header(self.user)
        self.headers_v1_1 = {**auth_header, **self._get_version_header('1.1.4')}
        self.headers_v1_2 = {**auth_header, **self._get_version_header('1.2')}
        self.resp_wrong_ver = {**auth_header, **self._get_version_header('-3')}
        self.resp_wrong_format = {**auth_header, 'HTTP_ACCEPT': f"application/vnd.bink+jso"}
        self.headers_no_ver = auth_header

    def _check_versioned_response(self, resp_v1_1, resp_v1_2, resp_no_ver, resp_wrong_ver, resp_wrong_format):
        self.assertEqual(resp_v1_1.get('X-API-Version'), '1.1')
        self.assertEqual(resp_v1_2.get('X-API-Version'), '1.2')
        self.assertEqual(resp_no_ver.get('X-API-Version'), '1.2')
        self.assertEqual(resp_wrong_ver.get('X-API-Version'), '1.2')
        self.assertIsNone(resp_wrong_format.get('X-API-Version'))

    def test_membership_plan_versioning(self):
        resp_v1_1 = self.client.get(reverse('membership-plans'), **self.headers_v1_1)
        resp_v1_2 = self.client.get(reverse('membership-plans'), **self.headers_v1_2)
        resp_no_ver = self.client.get(reverse('membership-plans'), **self.headers_no_ver)
        resp_wrong_ver = self.client.get(reverse('membership-plans'), **self.resp_wrong_ver)
        resp_wrong_format = self.client.get(reverse('membership-plans'), **self.resp_wrong_format)

        self._check_versioned_response(resp_v1_1, resp_v1_2, resp_no_ver, resp_wrong_ver, resp_wrong_format)

    def test_membership_plan_versioned_content(self):
        resp_v1_1 = self.client.get(reverse('membership-plan', args=[self.scheme.id]), **self.headers_v1_1)
        resp_v1_2 = self.client.get(reverse('membership-plan', args=[self.scheme.id]), **self.headers_v1_2)

        self.assertNotIn('fees', resp_v1_1.json()['account'])
        self.assertIn('fees', resp_v1_2.json()['account'])
        self.assertNotIn('content', resp_v1_1.json())
        self.assertIn('content', resp_v1_2.json())

    @patch('ubiquity.versioning.base.serializers.async_balance', autospec=True)
    @patch.object(MembershipTransactionsMixin, '_get_hades_transactions')
    @patch.object(SchemeAccount, 'get_midas_balance')
    def test_membership_card_versioning(self, *_):
        resp_v1_1 = self.client.get(reverse('membership-cards'), **self.headers_v1_1)
        resp_v1_2 = self.client.get(reverse('membership-cards'), **self.headers_v1_2)
        resp_no_ver = self.client.get(reverse('membership-cards'), **self.headers_no_ver)
        resp_wrong_ver = self.client.get(reverse('membership-cards'), **self.resp_wrong_ver)
        resp_wrong_format = self.client.get(reverse('membership-cards'), **self.resp_wrong_format)

        self._check_versioned_response(resp_v1_1, resp_v1_2, resp_no_ver, resp_wrong_ver, resp_wrong_format)

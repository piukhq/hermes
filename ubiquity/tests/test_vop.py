import json
from unittest.mock import patch

import httpretty
from django.conf import settings
from hermes.vop_tasks import send_activation, send_deactivation
from payment_card.tests.factories import IssuerFactory, PaymentCardAccountFactory, PaymentCardFactory
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from scheme.credentials import BARCODE, LAST_NAME, PASSWORD, CARD_NUMBER, PAYMENT_CARD_HASH
from scheme.models import SchemeBundleAssociation, SchemeCredentialQuestion
from scheme.tests.factories import (SchemeAccountFactory, SchemeBalanceDetailsFactory, SchemeCredentialAnswerFactory,
                                    SchemeCredentialQuestionFactory, SchemeFactory, SchemeBundleAssociationFactory)
from ubiquity.models import PaymentCardSchemeEntry, VopActivation, PaymentCardAccountEntry, SchemeAccountEntry
from ubiquity.tasks import deleted_membership_card_cleanup, deleted_payment_card_cleanup, deleted_service_cleanup
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory, ServiceConsentFactory
from ubiquity.tests.property_token import GenerateJWToken
from user.tests.factories import (ClientApplicationBundleFactory, ClientApplicationFactory, OrganisationFactory,
                                  UserFactory)


class RequestMock:
    channels_permit = None


class ChannelPermitMock:
    def __init__(self, client=None):
        self.client = client


class TestVOP(APITestCase):

    @classmethod
    def _get_auth_header(cls, user):
        token = GenerateJWToken(cls.client_app.organisation.name, cls.client_app.secret, cls.bundle.bundle_id,
                                user.external_id).get_token()
        return 'Bearer {}'.format(token)

    @classmethod
    def setUpTestData(cls):
        cls.metis_activate_url = settings.METIS_URL + '/visa/activate/'
        cls.metis_deactivate_url = settings.METIS_URL + '/visa/deactivate/'
        cls.metis_payment_service_url = settings.METIS_URL + '/payment_service/payment_card'
        organisation = OrganisationFactory(name='test_organisation')
        cls.client_app = ClientApplicationFactory(organisation=organisation, name='set up client application',
                                                  client_id='2zXAKlzMwU5mefvs4NtWrQNDNXYrDdLwWeSCoCCrjd8N0VBHoi')
        cls.bundle = ClientApplicationBundleFactory(bundle_id='test.auth.fake', client=cls.client_app)
        external_id = 'test@user.com'
        cls.user = UserFactory(external_id=external_id, client=cls.client_app, email=external_id)
        cls.scheme = SchemeFactory()
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
        cls.jwp_question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme,
            type=PAYMENT_CARD_HASH,
            label=PAYMENT_CARD_HASH,
            enrol_field=True,
            options=SchemeCredentialQuestion.OPTIONAL_JOIN
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
        cls.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=cls.scheme_account, user=cls.user)

        # Need to add an active association since it was assumed no setting was enabled
        cls.scheme_bundle_association = SchemeBundleAssociationFactory(
            scheme=cls.scheme,
            bundle=cls.bundle,
            status=SchemeBundleAssociation.ACTIVE
        )

        cls.scheme_account.update_barcode_and_card_number()

        cls.issuer = IssuerFactory(name='Barclays')
        cls.payment_card = PaymentCardFactory(slug='visa', system='visa')
        cls.pcard_hash1 = "some_hash"
        cls.pcard_hash2 = "5ae741975b4db7bc80072fe8f88f233ef4a67e1e1d7e3bbf68a314dfc6691636"
        cls.payment_token = "some_payment_token"
        cls.payment_card_account = PaymentCardAccountFactory(
            issuer=cls.issuer,
            payment_card=cls.payment_card,
            hash=cls.pcard_hash2,
            token=cls.payment_token,
            psp_token=cls.payment_token
        )
        cls.payment_card_account_entry = PaymentCardAccountEntryFactory(
            user=cls.user,
            payment_card_account=cls.payment_card_account
        )

        cls.auth_headers = {'HTTP_AUTHORIZATION': '{}'.format(cls._get_auth_header(cls.user))}
        cls.version_header = {"HTTP_ACCEPT": 'Application/json;v=1.1'}
        cls.service_headers = {'HTTP_AUTHORIZATION': f'Token {settings.SERVICE_API_KEY}'}

        cls.put_scheme = SchemeFactory()
        SchemeBalanceDetailsFactory(scheme_id=cls.put_scheme)

        cls.scheme_bundle_association_put = SchemeBundleAssociationFactory(
            scheme=cls.put_scheme,
            bundle=cls.bundle,
            status=SchemeBundleAssociation.ACTIVE
        )
        cls.put_scheme_manual_q = SchemeCredentialQuestionFactory(
            scheme=cls.put_scheme,
            type=CARD_NUMBER,
            label=CARD_NUMBER,
            manual_question=True
        )
        cls.put_scheme_scan_q = SchemeCredentialQuestionFactory(
            scheme=cls.put_scheme,
            type=BARCODE,
            label=BARCODE,
            scan_question=True
        )
        cls.put_scheme_auth_q = SchemeCredentialQuestionFactory(
            scheme=cls.put_scheme,
            type=PASSWORD,
            label=PASSWORD,
            auth_field=True
        )

        cls.wallet_only_scheme = SchemeFactory()
        cls.wallet_only_question = SchemeCredentialQuestionFactory(type=CARD_NUMBER, scheme=cls.wallet_only_scheme,
                                                                   manual_question=True)
        cls.scheme_bundle_association_put = SchemeBundleAssociationFactory(
            scheme=cls.wallet_only_scheme,
            bundle=cls.bundle,
            status=SchemeBundleAssociation.ACTIVE
        )

    def register_activation_request(self, metis_response):
        httpretty.register_uri(
            httpretty.POST,
            self.metis_activate_url,
            body=json.dumps(metis_response),
            status=201
        )

    def register_deactivation_request(self, metis_response):
        httpretty.register_uri(
            httpretty.POST,
            self.metis_deactivate_url,
            body=json.dumps(metis_response),
            status=201
        )

    def register_unenrol_request(self):
        httpretty.register_uri(
            httpretty.DELETE,
            self.metis_payment_service_url,
            body=json.dumps({}),
            status=200
        )

    @patch('ubiquity.models.send_deactivation.delay', autospec=True)
    @patch('hermes.vop_tasks.send_activation.delay', autospec=True)
    @patch('ubiquity.views.deleted_membership_card_cleanup.delay', autospec=True)
    @httpretty.activate
    def test_activate_and_deactivate_on_membership_card_delete(self, mock_delete, mock_activate, mock_deactivate):
        """
        :param mock_delete: Only the delay is mocked out allows call deleted_membership_card_cleanup with correct args
        :param mock_activate: Only the delay is mocked out allows call send_activation with correct args
        :param mock_deactivate: Only the delay is mocked out allows call send_deactivation with correct args
        """
        activation_id = "1234_activation_id"
        self.register_activation_request(
            {'response_status': 'Success', 'agent_response_code': 'Activate:SUCCESS',
             'agent_response_message': 'Success message;',
             'activation_id': activation_id}

        )

        self.register_deactivation_request({
            'response_status': 'Success', 'agent_response_code': 'Deactivate:SUCCESS',
            'agent_response_message': 'Success message;'})

        entry = PaymentCardSchemeEntry.objects.create(payment_card_account=self.payment_card_account,
                                                      scheme_account=self.scheme_account)

        entry.active_link = True
        entry.save()
        entry.vop_activate_check()
        self.assertTrue(mock_activate.called)

        # By pass celery delay to send activations by mocking delay getting parameters and calling without delay
        args = mock_activate.call_args

        send_activation(*args[0], **args[1])

        activations = VopActivation.objects.all()
        activate = activations[0]
        self.assertEqual(VopActivation.ACTIVATED, activate.status)
        self.assertEqual(activation_id, activate.activation_id)

        resp = self.client.delete(reverse('membership-card', args=[self.scheme_account.id]),
                                  data="{}",
                                  content_type='application/json', **self.auth_headers)

        # By pass deleted_membership_card_cleanup.delay by mocking delay getting parameters and calling without delay
        clean_up_args = mock_delete.call_args
        self.assertTrue(mock_delete.called)
        deleted_membership_card_cleanup(*clean_up_args[0], **clean_up_args[1])

        args = mock_deactivate.call_args
        self.assertTrue(mock_deactivate.called)
        send_deactivation(*args[0], **args[1])

        activations = VopActivation.objects.all()
        activate = activations[0]
        self.assertEqual(VopActivation.DEACTIVATED, activate.status)
        self.assertEqual(activation_id, activate.activation_id)

        self.assertEqual(resp.status_code, 200)
        link = PaymentCardSchemeEntry.objects.filter(pk=entry.pk)
        self.assertEqual(len(link), 0)

    @patch('hermes.vop_tasks.send_activation.delay', autospec=True)
    @patch('ubiquity.views.deleted_payment_card_cleanup.delay', autospec=True)
    @httpretty.activate
    def test_unenrol_and_deactivate_on_payment_card_delete(self, mock_delete, mock_activate):
        """
        :param mock_delete: Only the delay is mocked out allows call deleted_payment_card_cleanup with correct args
        :param mock_activate: Only the delay is mocked out allows call send_activation with correct args

        """
        activation_id = "1234_activation_id"
        self.register_activation_request(
            {'response_status': 'Success', 'agent_response_code': 'Activate:SUCCESS',
             'agent_response_message': 'Success message;',
             'activation_id': activation_id}

        )
        self.register_unenrol_request()
        entry = PaymentCardSchemeEntry.objects.create(payment_card_account=self.payment_card_account,
                                                      scheme_account=self.scheme_account)
        entry.active_link = True
        entry.save()
        entry.vop_activate_check()
        self.assertTrue(mock_activate.called)

        # By pass celery delay to send activations by mocking delay getting parameters and calling without delay
        args = mock_activate.call_args
        send_activation(*args[0], **args[1])

        activations = VopActivation.objects.all()
        activate = activations[0]
        self.assertEqual(VopActivation.ACTIVATED, activate.status)
        self.assertEqual(activation_id, activate.activation_id)

        self.client.delete(reverse('payment-card', args=[self.payment_card_account.id]),
                           data="{}", content_type='application/json', **self.auth_headers)

        # By pass deleted_membership_card_cleanup.delay by mocking delay getting parameters and calling without delay
        clean_up_args = mock_delete.call_args
        self.assertTrue(mock_delete.called)
        deleted_payment_card_cleanup(*clean_up_args[0], **clean_up_args[1])

        activations = VopActivation.objects.all()
        activate = activations[0]
        self.assertEqual(VopActivation.DEACTIVATING, activate.status)
        self.assertEqual(activation_id, activate.activation_id)

        # Now we have to simulate the metis call back by trapping request sent and compiling a success message
        metis_request = httpretty.last_request()
        metis_request_body = json.loads(metis_request.body)
        self.assertEqual(self.payment_card_account.id, metis_request_body['id'])
        self.assertEqual(self.payment_token, metis_request_body['payment_token'])
        self.assertEqual('visa', metis_request_body['partner_slug'])
        self.assertEqual(1, len(metis_request_body['activations']))
        deactivated_list = []
        for d in metis_request_body['activations'].keys():
            deactivated_list.append(int(d))

        resp_data = {
            "id": self.payment_card_account.id, "response_state": "Success", "response_status": "Delete:SUCCESS",
            "response_message": "Request proceed successfully without error.;", "response_action": "Delete",
            "retry_id": -1, "deactivated_list": deactivated_list, "deactivate_errors": {}
        }

        resp = self.client.put(reverse('update_payment_card_account_status'), data=json.dumps(resp_data),
                               content_type='application/json', **self.service_headers)

        activations = VopActivation.objects.all()
        activate = activations[0]
        self.assertEqual(VopActivation.DEACTIVATED, activate.status)
        self.assertEqual(activation_id, activate.activation_id)

        self.assertEqual(resp.status_code, 200)
        link = PaymentCardSchemeEntry.objects.filter(pk=entry.pk)
        self.assertEqual(len(link), 0)

    @patch('hermes.vop_tasks.send_activation.delay', autospec=True)
    @patch('ubiquity.views.deleted_service_cleanup.delay', autospec=True)
    @httpretty.activate
    def test_unenrol_and_deactivate_on_service_delete(self, mock_delete, mock_activate):
        """
        :param mock_delete: Only the delay is mocked out allows call deleted_payment_card_cleanup with correct args
        :param mock_activate: Only the delay is mocked out allows call send_activation with correct args

        """
        self.register_unenrol_request()

        # Create a service and set up cards
        user = UserFactory(external_id='test@delete.user', client=self.client_app, email='test@delete.user')
        ServiceConsentFactory(user=user)
        payment_card = PaymentCardFactory(slug="visa")
        pcard_1 = PaymentCardAccountFactory(payment_card=payment_card)
        pcard_2 = PaymentCardAccountFactory(payment_card=payment_card)
        mcard_1 = SchemeAccountFactory()
        mcard_2 = SchemeAccountFactory()

        PaymentCardAccountEntry.objects.create(user_id=user.id, payment_card_account_id=pcard_1.id)
        PaymentCardAccountEntry.objects.create(user_id=user.id, payment_card_account_id=pcard_2.id)

        SchemeAccountEntry.objects.create(user_id=user.id, scheme_account_id=mcard_1.id)
        SchemeAccountEntry.objects.create(user_id=user.id, scheme_account_id=mcard_2.id)

        entry1 = PaymentCardSchemeEntry.objects.create(payment_card_account=pcard_1,
                                                       scheme_account=mcard_1, active_link=True)

        entry2 = PaymentCardSchemeEntry.objects.create(payment_card_account=pcard_2, scheme_account=mcard_2,
                                                       active_link=True)

        activation_ids = {}
        # Run activations code for each entry
        for entry in [entry1, entry2]:
            pay_card_id = entry.payment_card_account.id
            activation_ids[pay_card_id] = f"activation_id_{pay_card_id}"
            self.register_activation_request(
                {'response_status': 'Success', 'agent_response_code': 'Activate:SUCCESS',
                 'agent_response_message': 'Success message;',
                 'activation_id': activation_ids[pay_card_id]}
            )

            entry.vop_activate_check()
            self.assertTrue(mock_activate.called)
            # By pass celery delay to send activations by mocking delay getting parameters and calling without delay
            args = mock_activate.call_args
            send_activation(*args[0], **args[1])

        activations = VopActivation.objects.all()
        for activation in activations:
            self.assertEqual(VopActivation.ACTIVATED, activation.status)
            self.assertEqual(activation_ids[activation.payment_card_account.id], activation.activation_id)
            print(activation.activation_id)

        auth_headers = {'HTTP_AUTHORIZATION': '{}'.format(self._get_auth_header(user))}
        response = self.client.delete(reverse('service'), **auth_headers)
        self.assertEqual(response.status_code, 200)

        # By pass deleted_service_cleanup.delay by mocking delay getting parameters and calling without delay
        clean_up_args = mock_delete.call_args
        self.assertTrue(mock_delete.called)
        deleted_service_cleanup(*clean_up_args[0], **clean_up_args[1])

        activations = VopActivation.objects.all()
        for activation in activations:
            self.assertEqual(VopActivation.DEACTIVATING, activation.status)
            self.assertEqual(activation_ids[activation.payment_card_account.id], activation.activation_id)
            print(activation.activation_id)

        # Now we have to simulate the metis call back by trapping request sent and compiling a success message
        metis_requests = httpretty.latest_requests()

        for metis_request in metis_requests:
            if 'activate' not in metis_request.path:
                metis_request_body = json.loads(metis_request.body)
                # self.assertEqual(self.payment_card_account.id, metis_request_body['id'])
                # self.assertEqual(self.payment_token, metis_request_body['payment_token'])
                self.assertEqual('visa', metis_request_body['partner_slug'])
                self.assertEqual(1, len(metis_request_body['activations']))
                deactivated_list = []
                for d in metis_request_body['activations'].keys():
                    deactivated_list.append(int(d))

                resp_data = {
                    "id": self.payment_card_account.id, "response_state": "Success",
                    "response_status": "Delete:SUCCESS",
                    "response_message": "Request proceed successfully without error.;", "response_action": "Delete",
                    "retry_id": -1, "deactivated_list": deactivated_list, "deactivate_errors": {}
                }

                self.client.put(reverse('update_payment_card_account_status'), data=json.dumps(resp_data),
                                content_type='application/json', **self.service_headers)

        activations = VopActivation.objects.all()
        for activation in activations:
            self.assertEqual(VopActivation.DEACTIVATED, activation.status)
            self.assertEqual(activation_ids[activation.payment_card_account.id], activation.activation_id)
            print(activation.activation_id)

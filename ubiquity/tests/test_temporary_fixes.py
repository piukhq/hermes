import datetime
from unittest.mock import patch

from django.conf import settings
from rest_framework.test import APITestCase

from payment_card.tests.factories import PaymentCardAccountFactory
from scheme.credentials import USER_NAME, CARD_NUMBER, PASSWORD
from scheme.models import SchemeCredentialQuestion, SchemeBundleAssociation
from scheme.tests.factories import (SchemeCredentialAnswerFactory, SchemeAccountFactory, SchemeBundleAssociationFactory,
                                    SchemeCredentialQuestionFactory, SchemeFactory)
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory
from user.tests.factories import UserFactory
from user.models import ClientApplication, ClientApplicationBundle


class TestTemporaryFixesBink(APITestCase):

    @classmethod
    def setUpClass(cls):
        cls.history_patcher = patch('history.signals.record_history', autospec=True)
        cls.history_patcher.start()

        cls.scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=cls.scheme,
                                        type=USER_NAME,
                                        manual_question=True)
        secondary_question = SchemeCredentialQuestionFactory(scheme=cls.scheme,
                                                             type=CARD_NUMBER,
                                                             third_party_identifier=True,
                                                             options=SchemeCredentialQuestion.LINK)
        password_question = SchemeCredentialQuestionFactory(scheme=cls.scheme,
                                                            type=PASSWORD,
                                                            options=SchemeCredentialQuestion.LINK_AND_JOIN)

        cls.scheme_account = SchemeAccountFactory(scheme=cls.scheme)
        cls.scheme_account_answer = SchemeCredentialAnswerFactory(question=cls.scheme.manual_question,
                                                                  scheme_account=cls.scheme_account)
        cls.second_scheme_account_answer = SchemeCredentialAnswerFactory(question=secondary_question,
                                                                         scheme_account=cls.scheme_account)

        cls.scheme_account_answer_password = SchemeCredentialAnswerFactory(answer="test_password",
                                                                           question=password_question,
                                                                           scheme_account=cls.scheme_account)
        cls.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=cls.scheme_account)
        cls.user = cls.scheme_account_entry.user

        cls.payment_card_account = PaymentCardAccountFactory()
        PaymentCardAccountEntryFactory(user=cls.user, payment_card_account=cls.payment_card_account)

        cls.scheme.save()
        cls.bink_client_app = ClientApplication.objects.get(client_id=settings.BINK_CLIENT_ID)
        cls.bundle = ClientApplicationBundle.objects.get(client=cls.bink_client_app, bundle_id='com.bink.wallet')
        cls.scheme_bundle_association = SchemeBundleAssociationFactory(scheme=cls.scheme, bundle=cls.bundle,
                                                                       status=SchemeBundleAssociation.ACTIVE)
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        cls.auth_service_headers = {'HTTP_AUTHORIZATION': 'Token ' + settings.SERVICE_API_KEY}

        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.history_patcher.stop()
        super().tearDownClass()

    @patch('analytics.api.update_attributes')
    @patch('analytics.api._get_today_datetime')
    def test_membership_card_creation_same_payment_card_lock(self, mock_date, *_):
        mock_date.return_value = datetime.datetime(year=2000, month=5, day=19)
        payload = {'scheme': self.scheme.id, USER_NAME: 'Test User', 'order': 0}
        new_user = UserFactory(client=self.user.client)
        PaymentCardAccountEntryFactory(user=new_user, payment_card_account=self.payment_card_account)
        auth_header = {'HTTP_AUTHORIZATION': 'Token ' + new_user.create_token()}

        resp = self.client.post('/schemes/accounts', data=payload, **auth_header)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(
            'An account for this scheme is already associated with one of the payment cards in your wallet.',
            resp.json().get('non_field_errors')
        )

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import serializers

from scheme.credentials import EMAIL, PASSWORD, POSTCODE, CARD_NUMBER
from scheme.models import SchemeCredentialQuestion, SchemeAccount
from scheme.serializers import JoinSerializer
from scheme.tests.factories import SchemeCredentialQuestionFactory, SchemeCredentialAnswerFactory, SchemeAccountFactory
from ubiquity.tasks import async_balance, async_all_balance, async_link, async_registration
from ubiquity.tests.factories import SchemeAccountEntryFactory
from user.tests.factories import UserFactory
from hermes.channels import Permit
from scheme.models import SchemeBundleAssociation
from user.tests.factories import ClientApplicationBundleFactory, ClientApplicationFactory, OrganisationFactory


class TestTasks(TestCase):

    def setUp(self):
        external_id = 'tasks@testbink.com'
        self.org = OrganisationFactory(name='Barclays')
        self.client = ClientApplicationFactory(organisation=self.org, name="Barclays-client")
        self.bundle = ClientApplicationBundleFactory(client=self.client)
        self.user = UserFactory(external_id=external_id, email=external_id)
        self.entry = SchemeAccountEntryFactory(user=self.user)
        self.entry2 = SchemeAccountEntryFactory(user=self.user)

        self.link_entry = SchemeAccountEntryFactory(user=self.user)
        self.link_scheme = self.link_entry.scheme_account.scheme
        self.manual_question = SchemeCredentialQuestionFactory(scheme=self.link_scheme, type=EMAIL,
                                                               manual_question=True)
        SchemeCredentialQuestionFactory(scheme=self.link_scheme, type=PASSWORD,
                                        options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=self.link_scheme, type=POSTCODE,
                                        options=SchemeCredentialQuestion.LINK_AND_JOIN)

    @patch('scheme.models.SchemeAccount.call_analytics')
    @patch('requests.get')
    def test_async_balance(self, mock_midas_balance, mock_analytics):
        scheme_account_id = self.entry.scheme_account.id
        scheme_slug = self.entry.scheme_account.scheme.slug
        async_balance(scheme_account_id)

        self.assertTrue(mock_analytics.called)
        self.assertTrue(mock_midas_balance.called)
        self.assertTrue(scheme_slug in mock_midas_balance.call_args[0][0])
        self.assertTrue(scheme_account_id in mock_midas_balance.call_args[1]['params'].values())

    @patch('ubiquity.tasks.async_balance.delay')
    def test_async_all_balance(self, mock_async_balance):
        user_id = self.user.id
        SchemeBundleAssociation.objects.create(bundle=self.bundle, scheme=self.entry.scheme_account.scheme)
        SchemeBundleAssociation.objects.create(bundle=self.bundle, scheme=self.entry2.scheme_account.scheme)
        channels_permit = Permit(self.bundle.bundle_id, client=self.bundle.client)

        async_all_balance(user_id, channels_permit=channels_permit)

        scheme_account = SchemeAccountFactory(is_deleted=True)
        deleted_entry = SchemeAccountEntryFactory(user=self.user, scheme_account=scheme_account)

        self.assertTrue(mock_async_balance.called)
        async_balance_call_args = [call_args[0][0] for call_args in mock_async_balance.call_args_list]
        self.assertTrue(self.entry.scheme_account.id in async_balance_call_args)
        self.assertTrue(self.entry2.scheme_account.id in async_balance_call_args)
        self.assertFalse(deleted_entry.scheme_account.id in async_balance_call_args)

    @patch('ubiquity.tasks.async_balance.delay')
    def test_async_all_balance_filtering(self, mock_async_balance):
        scheme_account_1 = SchemeAccountFactory()
        scheme_account_2 = SchemeAccountFactory(scheme=scheme_account_1.scheme)
        scheme_account_3 = SchemeAccountFactory(scheme=scheme_account_1.scheme)
        scheme_account_4 = SchemeAccountFactory(scheme=scheme_account_1.scheme)

        entry_active = SchemeAccountEntryFactory(user=self.user, scheme_account=scheme_account_1)
        user = entry_active.user
        SchemeBundleAssociation.objects.create(bundle=self.bundle, scheme=scheme_account_1.scheme)
        channels_permit = Permit(self.bundle.bundle_id, client=self.bundle.client)

        entry_pending = SchemeAccountEntryFactory(user=user, scheme_account=scheme_account_2)
        entry_invalid_credentials = SchemeAccountEntryFactory(user=user, scheme_account=scheme_account_3)
        entry_end_site_down = SchemeAccountEntryFactory(user=user, scheme_account=scheme_account_4)

        entry_pending.scheme_account.status = SchemeAccount.PENDING
        entry_pending.scheme_account.save()
        entry_invalid_credentials.scheme_account.status = SchemeAccount.INVALID_CREDENTIALS
        entry_invalid_credentials.scheme_account.save()
        entry_end_site_down.scheme_account.status = SchemeAccount.END_SITE_DOWN
        entry_end_site_down.scheme_account.save()

        async_all_balance(user.id, channels_permit=channels_permit)

        refreshed_scheme_accounts = [x[0][0] for x in mock_async_balance.call_args_list]
        self.assertIn(entry_active.scheme_account.id, refreshed_scheme_accounts)
        self.assertIn(entry_end_site_down.scheme_account.id, refreshed_scheme_accounts)
        self.assertNotIn(entry_invalid_credentials.scheme_account.id, refreshed_scheme_accounts)
        self.assertNotIn(entry_pending.scheme_account.id, refreshed_scheme_accounts)

    @patch('ubiquity.tasks.async_balance.delay')
    def test_async_all_balance_with_allowed_schemes(self, mock_async_balance):
        user_id = self.user.id
        SchemeBundleAssociation.objects.create(bundle=self.bundle, scheme=self.entry2.scheme_account.scheme)
        channels_permit = Permit(self.bundle.bundle_id, client=self.bundle.client)
        async_all_balance(user_id, channels_permit=channels_permit)
        self.assertTrue(mock_async_balance.called)
        async_balance_call_args = [call_args[0][0] for call_args in mock_async_balance.call_args_list]
        self.assertFalse(self.entry.scheme_account.id in async_balance_call_args)
        self.assertTrue(self.entry2.scheme_account.id in async_balance_call_args)

    @patch('scheme.models.SchemeAccount.call_analytics')
    @patch('requests.get')
    def test_async_link_validation_error(self, mock_midas_balance, mock_analytics):
        scheme_account = self.link_entry.scheme_account
        user_id = self.link_entry.user_id
        SchemeCredentialAnswerFactory(scheme_account=scheme_account, question=self.manual_question)

        auth_fields = {'password': 'test123'}
        self.assertEqual(scheme_account.status, scheme_account.ACTIVE)
        with self.assertRaises(serializers.ValidationError):
            async_link(auth_fields, scheme_account.id, user_id, False)

        scheme_account.refresh_from_db()
        self.assertEqual(scheme_account.status, scheme_account.INVALID_CREDENTIALS)
        self.assertFalse(mock_midas_balance.called)
        self.assertFalse(mock_analytics.called)

    @patch("analytics.api.update_scheme_account_attribute")
    @patch("scheme.mixins.SchemeAccountJoinMixin.post_midas_join")
    @patch("scheme.mixins.SchemeAccountJoinMixin.save_consents")
    def test_async_register_validation_failure(self, mock_save_consents, *_):
        mock_save_consents.side_effect = ValidationError("invalid consents")
        card_number = SchemeCredentialQuestionFactory(
            scheme=self.link_scheme,
            type=CARD_NUMBER,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            manual_question=True
        )

        SchemeCredentialAnswerFactory(
            scheme_account=self.link_entry.scheme_account,
            question=card_number,
            answer="1234567"
        )

        scheme_account_id = self.link_entry.scheme_account.id
        user_id = self.link_entry.user_id

        async_registration(user_id, JoinSerializer, scheme_account_id, {"credentials": {}}, self.bundle.bundle_id)

        self.link_entry.scheme_account.refresh_from_db()
        self.assertEqual(self.link_entry.scheme_account.status, SchemeAccount.REGISTRATION_FAILED)

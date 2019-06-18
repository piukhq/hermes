from unittest.mock import patch

from django.test import TestCase
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from scheme.credentials import EMAIL, PASSWORD, POSTCODE, CARD_NUMBER
from scheme.mixins import SchemeAccountJoinMixin
from scheme.models import SchemeCredentialQuestion, SchemeAccount
from scheme.tests.factories import SchemeCredentialQuestionFactory, SchemeCredentialAnswerFactory, SchemeAccountFactory
from ubiquity.tasks import async_balance, async_all_balance, async_link, async_join, async_registration
from ubiquity.tests.factories import SchemeAccountEntryFactory
from user.tests.factories import UserFactory


class TestTasks(TestCase):

    def setUp(self):
        external_id = 'tasks@testbink.com'
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
        async_all_balance(user_id)

        scheme_account = SchemeAccountFactory(is_deleted=True)
        deleted_entry = SchemeAccountEntryFactory(user=self.user, scheme_account=scheme_account)

        self.assertTrue(mock_async_balance.called)
        async_balance_call_args = [call_args[0][0] for call_args in mock_async_balance.call_args_list]
        self.assertTrue(self.entry.scheme_account.id in async_balance_call_args)
        self.assertTrue(self.entry2.scheme_account.id in async_balance_call_args)
        self.assertFalse(deleted_entry.scheme_account.id in async_balance_call_args)

    @patch('ubiquity.tasks.async_balance.delay')
    def test_async_all_balance_filtering(self, mock_async_balance):
        entry_active = SchemeAccountEntryFactory()
        user = entry_active.user
        entry_pending = SchemeAccountEntryFactory(user=user)
        entry_invalid_credentials = SchemeAccountEntryFactory(user=user)
        entry_end_site_down = SchemeAccountEntryFactory(user=user)

        entry_pending.scheme_account.status = SchemeAccount.PENDING
        entry_pending.scheme_account.save()
        entry_invalid_credentials.scheme_account.status = SchemeAccount.INVALID_CREDENTIALS
        entry_invalid_credentials.scheme_account.save()
        entry_end_site_down.scheme_account.status = SchemeAccount.END_SITE_DOWN
        entry_end_site_down.scheme_account.save()

        async_all_balance(user.id)

        refreshed_scheme_accounts = [x[0][0] for x in mock_async_balance.call_args_list]
        self.assertIn(entry_active.scheme_account.id, refreshed_scheme_accounts)
        self.assertIn(entry_end_site_down.scheme_account.id, refreshed_scheme_accounts)
        self.assertNotIn(entry_invalid_credentials.scheme_account.id, refreshed_scheme_accounts)
        self.assertNotIn(entry_pending.scheme_account.id, refreshed_scheme_accounts)

    @patch('ubiquity.tasks.async_balance.delay')
    def test_async_all_balance_with_allowed_schemes(self, mock_async_balance):
        user_id = self.user.id
        async_all_balance(user_id, allowed_schemes=[self.entry2.scheme_account.scheme.id])

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
            async_link(auth_fields, scheme_account.id, user_id)

        scheme_account.refresh_from_db()
        self.assertEqual(scheme_account.status, scheme_account.INVALID_CREDENTIALS)
        self.assertFalse(mock_midas_balance.called)
        self.assertFalse(mock_analytics.called)

    @patch.object(SchemeAccountJoinMixin, 'create_join_account')
    def test_async_join_validation_failure(self, mock_create_join_account):
        # This is just to break out of the function if the initial validation check hasn't failed
        mock_create_join_account.side_effect = ValidationError('Serializer validation did not fail but it should have')

        scheme_account_id = self.link_entry.scheme_account.id
        user_id = self.link_entry.user_id

        async_join(user_id, scheme_account_id, {})

        self.link_entry.scheme_account.refresh_from_db()
        self.assertEqual(self.link_entry.scheme_account.status, SchemeAccount.JOIN)

    @patch.object(SchemeAccountJoinMixin, 'create_join_account')
    def test_async_register_validation_failure(self, mock_create_join_account):
        # This is just to break out of the function if the initial validation check hasn't failed
        mock_create_join_account.side_effect = ValidationError('Serializer validation did not fail but it should have')

        card_number = SchemeCredentialQuestionFactory(
            scheme=self.link_scheme,
            type=CARD_NUMBER,
            options=SchemeCredentialQuestion.LINK_AND_JOIN,
            manual_question=True
        )

        SchemeCredentialAnswerFactory(
            scheme_account=self.link_entry.scheme_account,
            question=card_number,
            answer='1234567'
        )

        scheme_account_id = self.link_entry.scheme_account.id
        user_id = self.link_entry.user_id

        async_registration(user_id, scheme_account_id, {})

        self.link_entry.scheme_account.refresh_from_db()
        self.assertEqual(self.link_entry.scheme_account.status, SchemeAccount.JOIN)

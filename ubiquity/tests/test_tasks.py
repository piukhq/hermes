from django.test import TestCase
from unittest.mock import patch

from ubiquity.tasks import async_balance, async_all_balance
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

        self.assertTrue(mock_async_balance.called)
        async_balance_call_args = [call_args[0][0] for call_args in mock_async_balance.call_args_list]
        self.assertTrue(self.entry.scheme_account.id in async_balance_call_args)
        self.assertTrue(self.entry2.scheme_account.id in async_balance_call_args)

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

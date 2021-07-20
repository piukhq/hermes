from unittest.mock import patch

from history.models import HistoricalSchemeAccount
from history.utils import GlobalMockAPITestCase
from notification.tasks import SftpManager, NotificationProcessor
from ubiquity.tests.factories import SchemeAccountFactory


class TestNotificationTask(GlobalMockAPITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.test_org = "Barclays"
        cls.scheme_account = SchemeAccountFactory(user__client__organisation__name=cls.test_org)

    def test_get_data_initiation(self):
        test_notification = NotificationProcessor(organisation=self.test_org)
        data = test_notification.get_data()

        self.assertEqual(data[0][0], self.scheme_account.id)
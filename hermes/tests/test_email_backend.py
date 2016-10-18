from django.test import TestCase
from hermes.email_auth import EmailBackend
from user.tests.factories import UserFactory


class TestEmailBackend(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.user = UserFactory()
        cls.password = '!TestPassword12345'
        cls.user.set_password(cls.password)
        cls.user.save()
        cls.backend = EmailBackend()
        super().setUpClass()

    def test_successful_auth(self):
        user = self.backend.authenticate(username=self.user.email, password=self.password)
        self.assertEqual(user, self.user)

    def test_auth_with_invalid_password(self):
        user = self.backend.authenticate(username=self.user.email, password='!Gaogpanrparj124')
        self.assertIsNone(user)

    def test_auth_with_invalid_email(self):
        user = self.backend.authenticate(username='giojaogja@gaiowga.com', password=self.password)
        self.assertIsNone(user)

    def test_auth_with_kwargs_email(self):
        user = self.backend.authenticate(username=None, password=self.password, uid=self.user.email)
        self.assertEqual(user, self.user)

    def test_auth_with_natural_key(self):
        user = self.backend.authenticate(username=str(self.user.uid), password=self.password)
        self.assertEqual(user, self.user)

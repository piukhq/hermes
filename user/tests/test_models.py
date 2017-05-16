from django.test import TestCase
from user.models import Setting, UserSetting, CustomUser


class TestSettings(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.setting = Setting(slug='test-setting', value_type=Setting.NUMBER, default_value='10')
        super().setUpClass()

    def test_value_type_name(self):
        self.assertEqual('number', self.setting.value_type_name)

    def test_model_description(self):
        self.assertEqual('(number) test-setting: 10', str(self.setting))


class TestUserSettings(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = CustomUser(email='test@test.com')
        setting = Setting(slug='test-setting', value_type=Setting.NUMBER, default_value='10')
        cls.user_setting = UserSetting(user=cls.user, setting=setting, value='5')
        super().setUpClass()

    def test_model_description(self):
        self.assertEqual('test@test.com - test-setting: 5', str(self.user_setting))

    def test_to_boolean_true_value(self):
        user_setting = UserSetting(user=self.user, value='1')
        self.assertTrue(user_setting.to_boolean())

    def test_to_boolean_false_value(self):
        user_setting = UserSetting(user=self.user, value='0')
        self.assertFalse(user_setting.to_boolean())

    def test_to_boolean_invalid_value(self):
        user_setting = UserSetting(user=self.user, value='not_a_number')
        self.assertIsNone(user_setting.to_boolean())

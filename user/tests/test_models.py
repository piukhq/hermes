from history.utils import GlobalMockAPITestCase
from user.models import Setting, UserSetting, CustomUser, UserDetail


class TestSettings(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.setting = Setting(slug='test-setting', value_type=Setting.NUMBER, default_value='10')

    def test_value_type_name(self):
        self.assertEqual('number', self.setting.value_type_name)

    def test_model_description(self):
        self.assertEqual('(number) test-setting: 10', str(self.setting))


class TestUserSettings(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser(email='test@test.com')
        setting = Setting(slug='test-setting', value_type=Setting.NUMBER, default_value='10')
        cls.user_setting = UserSetting(user=cls.user, setting=setting, value='5')

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


class TestUserProfile(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser(email='test@test.com')
        cls.user_profile = UserDetail(user=cls.user)

    def test_set_field_no_conversion(self):
        phone_number = '123'
        self.user_profile.set_field('phone', phone_number)
        self.assertEqual(self.user_profile.phone, phone_number)

    def test_set_field_with_conversion(self):
        test_address_1 = '1 ascot road'
        self.user_profile.set_field('address_1', test_address_1)
        self.assertEqual(self.user_profile.address_line_1, test_address_1)

    def test_set_field_bad_attribute(self):
        with self.assertRaises(AttributeError):
            self.user_profile.set_field('bad_field', 'bad')

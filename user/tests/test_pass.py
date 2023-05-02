from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from history.utils import GlobalMockAPITestCase


class TestValidatePassword(GlobalMockAPITestCase):
    def test_password_too_short(self):
        expected_messages = ["This password is too short. It must contain at least 8 characters."]
        self.assertRaisesMessage(ValidationError, str(expected_messages), validate_password, password="aBc4")

    def test_password_has_no_numeric(self):
        expected_messages = ["This password is invalid. It must contain a numeric character."]
        self.assertRaisesMessage(ValidationError, str(expected_messages), validate_password, password="aBcDefgh")

    def test_password_has_no_upper_case_character(self):
        expected_messages = ["This password is invalid. It must contain an upper case character."]
        self.assertRaisesMessage(ValidationError, str(expected_messages), validate_password, password="a1cdefgh")

    def test_password_has_no_lower_case_character(self):
        expected_messages = ["This password is invalid. It must contain a lower case character."]
        self.assertRaisesMessage(ValidationError, str(expected_messages), validate_password, password="A123456789")

    def test_validate_message(self):
        expected_messages = [
            "This password is too short. It must contain at least 8 characters.",
            "This password is invalid. It must contain a numeric character.",
            "This password is invalid. It must contain an upper case character.",
        ]
        self.assertRaisesMessage(ValidationError, str(expected_messages), validate_password, password="abc")

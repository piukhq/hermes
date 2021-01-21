from history.utils import GlobalMockAPITestCase
from user.validators import validate_boolean, validate_number


class TestValidators(GlobalMockAPITestCase):
    def test_validate_boolean(self):
        self.assertTrue(validate_boolean('0'))
        self.assertTrue(validate_boolean('1'))
        self.assertFalse(validate_boolean('-1'))
        self.assertFalse(validate_boolean('2'))
        self.assertFalse(validate_boolean(''))
        self.assertFalse(validate_boolean(' '))
        self.assertFalse(validate_boolean('test'))

    def test_validate_number(self):
        self.assertTrue(validate_number('-1'))
        self.assertTrue(validate_number('0'))
        self.assertTrue(validate_number('1'))
        self.assertTrue(validate_number('51258'))
        self.assertTrue(validate_number('5123.515'))
        self.assertFalse(validate_number(''))
        self.assertFalse(validate_number(' '))
        self.assertFalse(validate_number('test'))

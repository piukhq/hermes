from unittest.mock import MagicMock
from django.core.exceptions import ValidationError
from django.test import TestCase
from scheme.admin import CredentialQuestionFormset


class TestCredentialsAdmin(TestCase):
    def create_instance(self, form_data):
        mocked_instance = MagicMock(spec=CredentialQuestionFormset)
        mocked_instance.instance = MagicMock()

        form = MagicMock()
        form.cleaned_data = form_data
        mocked_instance.forms = [form, form]
        return mocked_instance

    def test_clean_manual_error(self):
        mocked_instance = self.create_instance({'manual_question': True})

        with self.assertRaises(ValidationError) as e:
            CredentialQuestionFormset.clean(mocked_instance)
        self.assertEqual(e.exception.args[0], 'You may only select one manual question')

    def test_clean_scan_error(self):
        mocked_instance = self.create_instance({'scan_question': True, 'manual_question': False})

        with self.assertRaises(ValidationError) as e:
            CredentialQuestionFormset.clean(mocked_instance)
        self.assertEqual(e.exception.args[0], 'You may only select one scan question')

    def test_clean_active_and_no_manual(self):
        mocked_instance = self.create_instance({'scan_question': False, 'manual_question': False})
        mocked_instance.instance.is_active = True

        with self.assertRaises(ValidationError) as e:
            CredentialQuestionFormset.clean(mocked_instance)
        self.assertEqual(e.exception.args[0], 'You must have a manual question when a scheme is set to active')

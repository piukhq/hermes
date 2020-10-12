from unittest.mock import MagicMock

from django.core.exceptions import ValidationError
from django.test import TestCase

from scheme.admin import CredentialQuestionFormset
from scheme.forms import SchemeForm
from scheme.tests.factories import CategoryFactory, SchemeFactory


class MockCredentialQuestionFormset(MagicMock):

    def _collect_form_data(self):
        manual_questions = [form.cleaned_data['manual_question'] for form in self.forms]
        return manual_questions, [], []


class TestCredentialsAdmin(TestCase):
    def create_instance(self, form_data):
        mocked_instance = MockCredentialQuestionFormset(spec=CredentialQuestionFormset)
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


class TestSchemeValidation(TestCase):
    def setUp(self):
        self.scheme = SchemeFactory()

    def test_valid_point_name(self):
        cat = CategoryFactory()
        form = SchemeForm(instance=self.scheme, data={
            'category': cat.id,
            'company': 'test',
            'forgotten_password_url': 'www.test.com',
            'name': 'test',
            'scan_message': 'test',
            'slug': 'test',
            'tier': 1,
            'transaction_headers': "Date,Reference,Points",
            'url': 'www.test.com',
            'point_name': 'valid',
            'max_points_value_length': 2,
            'status': 0,
        })
        self.assertTrue(form.is_valid(), msg=repr(form.errors))

    def test_invalid_point_name(self):
        cat = CategoryFactory()
        form = SchemeForm(instance=self.scheme, data={
            'category': cat.id,
            'company': 'test',
            'forgotten_password_url': 'www.test.com',
            'name': 'test',
            'scan_message': 'test',
            'slug': 'test',
            'tier': 1,
            'url': 'www.test.com',
            'point_name': 'itsinvalid',
            'max_points_value_length': 2
        })
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['point_name'][0], 'The length of the point name added to the maximum points value '
                                                       'length must not exceed 10')

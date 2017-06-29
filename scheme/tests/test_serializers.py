from django.test import TestCase
from rest_framework.exceptions import ValidationError
from scheme.serializers import CreateSchemeAccountSerializer, SchemeSerializer, \
    LinkSchemeSerializer, OneQuestionLinkSchemeSerializer
from scheme.tests.factories import SchemeCredentialQuestionFactory, SchemeAccountFactory, SchemeFactory
from scheme.credentials import BARCODE
from unittest.mock import MagicMock, patch

from user.tests.factories import UserFactory


class TestCreateSchemeAccountSerializer(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = UserFactory()
        request = MagicMock()
        request.user = cls.user
        cls.serializer = CreateSchemeAccountSerializer()
        cls.serializer.context['request'] = request
        super().setUpClass()

    def test_allowed_answers(self):
        question = SchemeCredentialQuestionFactory(type=BARCODE, scan_question=True)
        allowed_answers = CreateSchemeAccountSerializer.allowed_answers(question.scheme)
        self.assertEqual(allowed_answers, [BARCODE, ])

    def test_validate_no_scheme(self):
        with self.assertRaises(ValidationError) as e:
            self.serializer.validate({'scheme': 2342342})
        self.assertEqual(e.exception.detail[0], "Scheme '2342342' does not exist")

    def test_validate_existing_scheme_account(self):
        question = SchemeCredentialQuestionFactory(type=BARCODE, manual_question=True)
        scheme_account = SchemeAccountFactory(scheme=question.scheme, user=self.user)
        self.serializer.context['view'] = ''
        with self.assertRaises(ValidationError) as e:
            self.serializer.validate({'scheme': scheme_account.scheme.id})
        self.assertTrue(e.exception.detail[0].startswith('You already have an account for this scheme'))

    def test_validate_answer_types(self):
        question = SchemeCredentialQuestionFactory(type=BARCODE, manual_question=True)
        with self.assertRaises(ValidationError) as e:
            self.serializer.validate({'scheme': question.scheme.id})
        self.assertEqual(e.exception.detail[0], "You must submit one scan or manual question answer")

    def test_validate_bad_question_type(self):
        question = SchemeCredentialQuestionFactory(type=BARCODE, manual_question=True)
        with self.assertRaises(ValidationError) as e:
            self.serializer.validate({'scheme': question.scheme.id, 'email': "dfg@gmail.com"})
        self.assertEqual(e.exception.detail[0], "Your answer type 'email' is not allowed")


class TestAnswerValidation(TestCase):
    def test_email_validation_error(self):
        serializer = LinkSchemeSerializer(data={"email": "bobgmail.com"})
        self.assertFalse(serializer.is_valid())

    def test_memorable_date_validation_error(self):
        serializer = LinkSchemeSerializer(data={"memorable_date": "122/11/2015"})
        self.assertFalse(serializer.is_valid())

    @patch.object(LinkSchemeSerializer, 'validate')
    def test_memorable_date_validation(self, mock_validate):
        serializer = LinkSchemeSerializer(data={"memorable_date": "22/11/2015"})
        self.assertTrue(serializer.is_valid())

    def test_pin_validation_error(self):
        serializer = LinkSchemeSerializer(data={"pin": "das33"})
        self.assertFalse(serializer.is_valid())

    @patch.object(LinkSchemeSerializer, 'validate')
    def test_pin_validation(self, mock_validate):
        serializer = LinkSchemeSerializer(data={"pin": "3333"})
        self.assertTrue(serializer.is_valid())


class TestSchemeSerializer(TestCase):
    def test_get_link_questions(self):
        scheme = SchemeFactory()
        question = SchemeCredentialQuestionFactory(type=BARCODE, scheme=scheme)
        serializer = SchemeSerializer()

        data = serializer.get_link_questions(scheme)
        self.assertEqual(data[0]['id'], question.id)
        self.assertEqual(data[0]['type'], BARCODE)

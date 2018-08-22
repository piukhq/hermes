from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from scheme.credentials import BARCODE, CARD_NUMBER, FIRST_NAME, LAST_NAME, PASSWORD, TITLE
from scheme.models import SchemeCredentialQuestion
from scheme.serializers import CreateSchemeAccountSerializer, JoinSerializer, LinkSchemeSerializer, SchemeSerializer
from scheme.tests.factories import (SchemeCredentialQuestionFactory, SchemeFactory)
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

    @patch.object(JoinSerializer, 'validate')
    def test_date_of_birth_validation(self, mock_validate):
        serializer = JoinSerializer(data={
            "save_user_information": "true",
            "order": 0,
            "date_of_birth": "22/11/1999"
        })
        self.assertTrue(serializer.is_valid())


class TestSchemeSerializer(TestCase):
    def test_get_link_questions(self):
        scheme = SchemeFactory()
        question = SchemeCredentialQuestionFactory(type=BARCODE, scheme=scheme, options=SchemeCredentialQuestion.LINK)
        merchant_identifier_question = SchemeCredentialQuestionFactory(
            type=TITLE, scheme=scheme, options=SchemeCredentialQuestion.MERCHANT_IDENTIFIER
        )
        serializer = SchemeSerializer()

        data = serializer.get_link_questions(scheme)
        question_ids = [x['id'] for x in data]
        question_types = [x['type'] for x in data]
        self.assertIn(question.id, question_ids)
        self.assertNotIn(merchant_identifier_question.id, question_ids)
        self.assertIn(BARCODE, question_types)
        self.assertNotIn(TITLE, question_types)

    def test_get_join_questions(self):
        scheme = SchemeFactory()
        question = SchemeCredentialQuestionFactory(type=BARCODE, scheme=scheme,
                                                   options=SchemeCredentialQuestion.LINK_AND_JOIN, manual_question=True)
        question2 = SchemeCredentialQuestionFactory(type=LAST_NAME, scheme=scheme,
                                                    options=SchemeCredentialQuestion.OPTIONAL_JOIN)
        question3 = SchemeCredentialQuestionFactory(type=PASSWORD, scheme=scheme, options=SchemeCredentialQuestion.JOIN)
        link_question = SchemeCredentialQuestionFactory(type=FIRST_NAME, scheme=scheme,
                                                        options=SchemeCredentialQuestion.LINK)
        none_question = SchemeCredentialQuestionFactory(type=TITLE, scheme=scheme,
                                                        options=SchemeCredentialQuestion.NONE)
        merchant_question = SchemeCredentialQuestionFactory(type=CARD_NUMBER, scheme=scheme,
                                                            options=SchemeCredentialQuestion.MERCHANT_IDENTIFIER)
        serializer = SchemeSerializer()

        data = serializer.get_join_questions(scheme)
        data_types = [x['type'] for x in data]
        join_question_types = [question.type, question2.type, question3.type]
        not_join_questions_types = [link_question.type, none_question.type, merchant_question.type]

        self.assertTrue(all(x in join_question_types for x in data_types))
        self.assertFalse(any(x in not_join_questions_types for x in data_types))

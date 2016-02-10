from django.test import TestCase
from scheme.credentials import PASSWORD
from scheme.tests.factories import SchemeCredentialAnswerFactory, SchemeCredentialQuestionFactory


class TestCredentials(TestCase):
    def test_clean_answer(self):
        question = SchemeCredentialQuestionFactory(type=PASSWORD)
        answer = SchemeCredentialAnswerFactory(answer='sdfsdfsdf', question=question)
        self.assertEqual(answer.clean_answer(), '****')

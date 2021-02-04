from history.utils import GlobalMockAPITestCase
from scheme.credentials import PASSWORD
from scheme.tests.factories import SchemeCredentialAnswerFactory, SchemeCredentialQuestionFactory


class TestCredentials(GlobalMockAPITestCase):
    def test_clean_answer(self):
        question = SchemeCredentialQuestionFactory(type=PASSWORD)
        answer = SchemeCredentialAnswerFactory(answer='sdfsdfsdf', question=question)
        self.assertEqual(answer.clean_answer(), '****')

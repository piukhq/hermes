from rest_framework.test import APITestCase
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from scheme.tests.factories import SchemeCredentialQuestionFactory, SchemeImageFactory, SchemeFactory
from scheme.credentials import EMAIL, BARCODE
from django.test import TestCase

from user.tests.factories import UserFactory


class TestSchemeViews(APITestCase):
    @classmethod
    def setUpClass(cls):
        user = UserFactory()
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + user.create_token()}
        super().setUpClass()

    def test_scheme_list(self):
        scheme = SchemeFactory()
        question = SchemeCredentialQuestionFactory(scheme=scheme)
        scheme.manual_question = question
        scheme.save()
        response = self.client.get('/schemes/', **self.auth_headers)

        self.assertEqual(response.status_code, 200,)
        self.assertEqual(type(response.data), ReturnList)
        self.assertIn('has_points', response.data[0])
        self.assertIn('has_transactions', response.data[0])
        self.assertIn('link_questions', response.data[0])

    def test_scheme_item(self):
        scheme = SchemeFactory()
        SchemeImageFactory(scheme=scheme)
        link_question = SchemeCredentialQuestionFactory.create(scheme=scheme, type=EMAIL)
        question = SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE)
        scheme.manual_question = question
        scheme.save()

        response = self.client.get('/schemes/{0}'.format(scheme.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], scheme.id)
        self.assertEqual(len(response.data['images']), 1)
        self.assertEqual(response.data['link_questions'][0]['id'], link_question.id)


class TestSchemeModel(TestCase):
    def test_link_questions(self):
        scheme = SchemeFactory()
        barcode_question = SchemeCredentialQuestionFactory(type=BARCODE, scheme=scheme)
        email_question = SchemeCredentialQuestionFactory(type=EMAIL, scheme=scheme)
        scheme.manual_question = barcode_question
        scheme.save()
        link_questions = scheme.link_questions
        self.assertEqual(len(link_questions), 1)
        self.assertEqual(link_questions[0].id, email_question.id)

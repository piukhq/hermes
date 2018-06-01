from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from django.test import TestCase
from django.conf import settings
from django.utils import timezone

from scheme.tests.factories import SchemeCredentialQuestionFactory, SchemeImageFactory, SchemeFactory, SettingsFactory
from scheme.credentials import EMAIL, BARCODE, CARD_NUMBER, TITLE
from scheme.models import SchemeCredentialQuestion
from user.tests.factories import UserFactory
from common.models import Image
from user.models import Setting


class TestSchemeImages(APITestCase):

    @classmethod
    def setUpClass(cls):
        user = UserFactory()
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + user.create_token()}
        cls.image = SchemeImageFactory(status=Image.DRAFT,
                                       start_date=timezone.now() - timezone.timedelta(hours=1),
                                       end_date=timezone.now() + timezone.timedelta(hours=1))

        SchemeCredentialQuestionFactory(scheme=cls.image.scheme, options=SchemeCredentialQuestion.LINK)

        super().setUpClass()

    def test_no_draft_images_in_schemes_list(self):
        resp = self.client.get('/schemes', **self.auth_headers)
        our_scheme = [s for s in resp.json() if s['slug'] == self.image.scheme.slug][0]
        self.assertEqual(0, len(our_scheme['images']))

        self.image.status = Image.PUBLISHED
        self.image.save()

        resp = self.client.get('/schemes', **self.auth_headers)
        our_scheme = [s for s in resp.json() if s['slug'] == self.image.scheme.slug][0]
        self.assertEqual(1, len(our_scheme['images']))


class TestSchemeViews(APITestCase):

    @classmethod
    def setUpClass(cls):
        user = UserFactory()
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + user.create_token()}
        super().setUpClass()

    def test_scheme_list(self):
        SchemeCredentialQuestionFactory(manual_question=True)
        SchemeFactory()
        response = self.client.get('/schemes/', **self.auth_headers)

        self.assertEqual(response.status_code, 200,)
        self.assertEqual(type(response.data), ReturnList)
        self.assertIn('has_points', response.data[0])
        self.assertIn('has_transactions', response.data[0])
        self.assertIn('link_questions', response.data[0])
        self.assertIn('join_questions', response.data[0])
        self.assertIn('preferences', response.data[0])

        self.assertIn('join', response.data[0]['preferences'], "no join section in preferences")
        self.assertIn('link', response.data[0]['preferences'], "no link section in preferences")

        # make sure there are no schemes that don't have questions
        for row in response.data:
            self.assertTrue(
                len(row['link_questions']) > 0 or
                len(row['join_questions']) > 0 or
                row['manual_question'] is not None or
                row['scan_question'] is not None)

    def test_scheme_preferences(self):
        scheme2 = SchemeFactory()
        SchemeImageFactory(scheme=scheme2)
        SchemeCredentialQuestionFactory.create(
            scheme=scheme2,
            type=EMAIL,
            options=SchemeCredentialQuestion.LINK)
        SchemeCredentialQuestionFactory.create(
            scheme=scheme2,
            type=CARD_NUMBER,
            options=SchemeCredentialQuestion.JOIN,
            manual_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme2, type=BARCODE, manual_question=True)
        SettingsFactory.create(scheme=scheme2)

        scheme = SchemeFactory()
        SchemeImageFactory(scheme=scheme)
        SchemeCredentialQuestionFactory.create(
            scheme=scheme,
            type=EMAIL,
            options=SchemeCredentialQuestion.LINK)
        SchemeCredentialQuestionFactory.create(
            scheme=scheme,
            type=CARD_NUMBER,
            options=SchemeCredentialQuestion.JOIN,
            manual_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE, manual_question=True)

        link_message = "Link Message"
        join_message = "Join Message"
        test_string = "Test default String"
        test_string2 = "Test disabled default String"
        SettingsFactory.create(scheme=scheme, journey=Setting.LINK_JOIN, slug="tm1", order=2,
                               value_type=Setting.STRING,
                               default_value=test_string)
        SettingsFactory.create(scheme=scheme, journey=Setting.LINK_JOIN, slug="tm2", order=3, is_enabled=False,
                               value_type=Setting.STRING,
                               default_value=test_string2)
        SettingsFactory.create(scheme=scheme, journey=Setting.LINK, default_value=link_message)
        SettingsFactory.create(scheme=scheme, journey=Setting.JOIN, default_value=join_message)
        response = self.client.get('/schemes/{0}'.format(scheme.id), **self.auth_headers)
        self.assertIn('preferences', response.data, "no preferences section")
        join_data = response.data['preferences']['join']
        link_data = response.data['preferences']['link']
        self.assertEqual(join_data[0]['default_value'], join_message, "Missing Join TEXT preferences")
        self.assertEqual(link_data[0]['default_value'], link_message, "Missing Link TEXT preferences")
        self.assertEqual(join_data[1]['default_value'], test_string, "Missing Join default String preference")
        self.assertEqual(link_data[1]['default_value'], test_string, "Missing Link default String preference")
        self.assertEqual(join_data[1]['slug'], "tm1", "Incorrect Join preference slug")
        self.assertEqual(link_data[1]['slug'], "tm1", "Incorrect Link preference slug")
        self.assertEqual(len(link_data), 2, "Disabled Field present in link preferences")
        self.assertEqual(len(join_data), 2, "Disabled Field present in join preferences")

    def test_scheme_item(self):
        scheme = SchemeFactory()
        SchemeImageFactory(scheme=scheme)
        link_question = SchemeCredentialQuestionFactory.create(scheme=scheme,
                                                               type=EMAIL,
                                                               options=SchemeCredentialQuestion.LINK)
        join_question = SchemeCredentialQuestionFactory.create(scheme=scheme,
                                                               type=CARD_NUMBER,
                                                               options=SchemeCredentialQuestion.JOIN,
                                                               manual_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE, manual_question=True)

        response = self.client.get('/schemes/{0}'.format(scheme.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], scheme.id)
        self.assertEqual(len(response.data['images']), 1)
        self.assertEqual(response.data['link_questions'][0]['id'], link_question.id)
        self.assertEqual(response.data['join_questions'][0]['id'], join_question.id)

    def test_get_reference_images(self):
        scheme = SchemeFactory()
        SchemeImageFactory(scheme=scheme, image_type_code=5)

        response = self.client.get('/schemes/images/reference',
                                   HTTP_AUTHORIZATION='Token {}'.format(settings.SERVICE_API_KEY))
        self.assertEqual(response.status_code, 200)

        json = response.json()
        self.assertEqual(type(json), list)
        self.assertIn('file', json[0])
        self.assertIn('scheme_id', json[0])

    @patch('scheme.views.requests.post')
    def test_identify_image(self, mock_post):
        scheme = SchemeFactory()
        SchemeImageFactory(scheme=scheme, image_type_code=5)

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'status': 'success',
            'reason': '',
            'scheme_id': '5'
        }

        response = self.client.post('/schemes/identify', data={'base64img': 'test'},
                                    **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['scheme_id'], 5)


class TestSchemeModel(TestCase):

    def test_link_questions(self):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(type=BARCODE, scheme=scheme, manual_question=True)
        email_question = SchemeCredentialQuestionFactory(type=EMAIL,
                                                         scheme=scheme,
                                                         options=SchemeCredentialQuestion.LINK)
        phone_question = SchemeCredentialQuestionFactory(type=TITLE,
                                                         scheme=scheme,
                                                         options=SchemeCredentialQuestion.LINK_AND_JOIN)

        link_questions = scheme.link_questions
        self.assertEqual(len(link_questions), 2)
        self.assertEqual(link_questions[0].id, phone_question.id)
        self.assertEqual(link_questions[1].id, email_question.id)

    def test_join_questions(self):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(type=BARCODE,
                                        scheme=scheme,
                                        manual_question=True,
                                        options=SchemeCredentialQuestion.JOIN)
        non_join_question = SchemeCredentialQuestionFactory(type=CARD_NUMBER, scheme=scheme, manual_question=True)
        email_question = SchemeCredentialQuestionFactory(type=EMAIL,
                                                         scheme=scheme,
                                                         options=SchemeCredentialQuestion.LINK_AND_JOIN)
        optional_question = SchemeCredentialQuestionFactory(type=TITLE,
                                                            scheme=scheme,
                                                            options=SchemeCredentialQuestion.OPTIONAL_JOIN)

        join_questions = scheme.join_questions
        self.assertEqual(len(join_questions), 3)
        self.assertIn(email_question.id, [question.id for question in scheme.join_questions])
        self.assertIn(optional_question.id, [question.id for question in scheme.join_questions])
        self.assertNotIn(non_join_question.id, [question.id for question in scheme.join_questions])

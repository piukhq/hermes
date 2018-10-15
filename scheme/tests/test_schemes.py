from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from django.test import TestCase
from django.conf import settings
from django.utils import timezone

from scheme.tests.factories import SchemeCredentialQuestionFactory, SchemeImageFactory, SchemeFactory, ConsentFactory, \
    SchemeCredentialQuestionChoiceFactory, SchemeCredentialQuestionChoiceValueFactory, ControlFactory
from scheme.credentials import EMAIL, BARCODE, CARD_NUMBER, TITLE
from scheme.models import SchemeCredentialQuestion, Control
from user.tests.factories import UserFactory
from common.models import Image
from scheme.models import JourneyTypes


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
        self.assertIn('consents', response.data[0])

        # make sure there are no schemes that don't have questions
        for row in response.data:
            self.assertTrue(
                len(row['link_questions']) > 0 or
                len(row['join_questions']) > 0 or
                row['manual_question'] is not None or
                row['scan_question'] is not None)

    def test_scheme_consents(self):
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
        ConsentFactory.create(scheme=scheme2)

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
        test_string = "Test disabled default String"
        tm1 = ConsentFactory.create(
            scheme=scheme, journey=JourneyTypes.LINK.value, order=2,
            check_box=True, text=link_message, required=False
        )

        tm2 = ConsentFactory.create(
            scheme=scheme, journey=JourneyTypes.JOIN.value, order=3, is_enabled=False,
            check_box=True, text=test_string
        )
        ConsentFactory.create(scheme=scheme, journey=JourneyTypes.LINK.value, text=link_message)
        ConsentFactory.create(scheme=scheme, journey=JourneyTypes.JOIN.value, text=join_message)
        response = self.client.get('/schemes/{0}'.format(scheme.id), **self.auth_headers)
        self.assertIn('consents', response.data, "no consents section in /schemes/# ")

        found = False
        for consent in response.data['consents']:
            if consent['id'] == tm1.id:
                self.assertEqual(consent['text'], link_message, "Missing/incorrect Link TEXT consents")
                self.assertEqual(consent['check_box'], True, "Missing/incorrect check box in consents")
                self.assertEqual(consent['journey'], JourneyTypes.LINK.value, "Missing/incorrect journey in consents")
                self.assertEqual(consent['required'], False, "Missing/incorrect required in consents")
                self.assertEqual(consent['order'], 2, "Missing/incorrect required in consents")
                found = True
            elif consent['id'] == tm2.id:
                self.assertTrue(False, "Disabled slug present")

        self.assertTrue(found, "Test consent not found in /scheme/#")

    def test_scheme_transaction_headers(self):
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

        response = self.client.get('/schemes/{0}'.format(scheme.id), **self.auth_headers)
        expected_transaction_headers = [{"name": "header 1"}, {"name": "header 2"}, {"name": "header 3"}]
        self.assertListEqual(expected_transaction_headers, response.data["transaction_headers"])

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

    def test_scheme_item_with_question_choices(self):
        scheme = SchemeFactory()
        manual_question = SchemeCredentialQuestionFactory(type=CARD_NUMBER, scheme=scheme, manual_question=True,
                                                          options=SchemeCredentialQuestion.NONE)
        link_question = SchemeCredentialQuestionFactory(type=TITLE, scheme=scheme,
                                                        options=SchemeCredentialQuestion.LINK)
        join_question = SchemeCredentialQuestionFactory(type=BARCODE, scheme=scheme,
                                                        options=SchemeCredentialQuestion.JOIN)

        choice_1 = SchemeCredentialQuestionChoiceFactory(scheme=scheme, scheme_question=link_question)
        SchemeCredentialQuestionChoiceFactory(scheme=scheme, scheme_question=join_question)

        SchemeCredentialQuestionChoiceValueFactory(choice=choice_1, value='Mr')
        SchemeCredentialQuestionChoiceValueFactory(choice=choice_1, value='MRS')
        SchemeCredentialQuestionChoiceValueFactory(choice=choice_1, value='miss')

        response = self.client.get('/schemes/{0}'.format(scheme.id), **self.auth_headers)
        data = response.json()

        self.assertEqual(data['link_questions'][0]['id'], link_question.id)
        self.assertEqual(set(data['link_questions'][0]['question_choices']), {'Mr', 'MRS', 'miss'})
        self.assertEqual(len(data['link_questions'][0]['question_choices']), 3)

        self.assertEqual(data['join_questions'][0]['id'], join_question.id)
        self.assertEqual(len(data['join_questions'][0]['question_choices']), 0)

        self.assertEqual(data['manual_question']['id'], manual_question.id)
        self.assertEqual(len(data['manual_question']['question_choices']), 0)

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

    @patch('scheme.mixins.requests.post')
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
        self.assertIn(email_question.id, [question.id for question in link_questions])
        self.assertIn(phone_question.id, [question.id for question in link_questions])

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
        self.assertIn(email_question.id, [question.id for question in join_questions])
        self.assertIn(optional_question.id, [question.id for question in join_questions])
        self.assertNotIn(non_join_question.id, [question.id for question in join_questions])

    def test_scheme_question_choices(self):
        scheme = SchemeFactory()
        question_1 = SchemeCredentialQuestionFactory(type=BARCODE, scheme=scheme, manual_question=True,
                                                     options=SchemeCredentialQuestion.LINK)
        question_2 = SchemeCredentialQuestionFactory(type=CARD_NUMBER, scheme=scheme,
                                                     options=SchemeCredentialQuestion.JOIN)
        question_3 = SchemeCredentialQuestionFactory(type=TITLE, scheme=scheme,
                                                     options=SchemeCredentialQuestion.LINK_AND_JOIN)

        choice_1 = SchemeCredentialQuestionChoiceFactory(scheme=scheme, scheme_question=question_3)
        SchemeCredentialQuestionChoiceFactory(scheme=scheme, scheme_question=question_2)

        SchemeCredentialQuestionChoiceValueFactory(choice=choice_1, value='Mr')
        SchemeCredentialQuestionChoiceValueFactory(choice=choice_1, value='Mrs')
        SchemeCredentialQuestionChoiceValueFactory(choice=choice_1, value='Miss')

        self.assertEqual(len(question_1.question_choices), 0)
        self.assertEqual(len(question_2.question_choices), 0)
        self.assertEqual(len(question_3.question_choices), 3)
        self.assertEqual(set(question_3.question_choices), {'Mrs', 'Mr', 'Miss'})

    def test_scheme_controls(self):
        scheme = SchemeFactory()
        control1 = ControlFactory(key=Control.JOIN_KEY, label='hello', hint_text='world', scheme=scheme)
        control2 = ControlFactory(key=Control.ADD_KEY, label='things', hint_text='stuff', scheme=scheme)

        self.assertEqual(control1.scheme, scheme)
        self.assertEqual(control2.scheme, scheme)
        self.assertEqual(set(control1.KEY_CHOICES),
                         {('join_button', 'Join Button - Add Card screen'),
                          ('add_button', 'Add Button - Add Card screen')})
        self.assertEqual(set(control2.KEY_CHOICES),
                         {('join_button', 'Join Button - Add Card screen'),
                          ('add_button', 'Add Button - Add Card screen')})

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from history.utils import GlobalMockAPITestCase
from scheme.serializers import ControlSerializer
from scheme.tests.factories import ControlFactory
from scheme.models import Control, Consent
from unittest.mock import MagicMock, patch

from scheme.credentials import BARCODE, CARD_NUMBER, FIRST_NAME, LAST_NAME, PASSWORD, TITLE
from scheme.models import ConsentStatus, JourneyTypes, SchemeCredentialQuestion
from scheme.serializers import (CreateSchemeAccountSerializer, JoinSerializer, LinkSchemeSerializer,
                                SchemeSerializer, UpdateUserConsentSerializer,
                                UserConsentSerializer)
from scheme.tests.factories import (ConsentFactory, SchemeAccountFactory, SchemeCredentialQuestionFactory,
                                    SchemeFactory, UserConsentFactory)
from ubiquity.tests.factories import SchemeAccountEntryFactory
from user.tests.factories import UserFactory
from unittest.mock import MagicMock, patch

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from history.utils import GlobalMockAPITestCase
from scheme.credentials import BARCODE, CARD_NUMBER, FIRST_NAME, LAST_NAME, PASSWORD, TITLE
from scheme.models import Control, Consent, ConsentStatus, JourneyTypes, SchemeCredentialQuestion
from scheme.serializers import ControlSerializer, CreateSchemeAccountSerializer, JoinSerializer, LinkSchemeSerializer, \
    SchemeSerializer, UpdateUserConsentSerializer, UserConsentSerializer
from scheme.tests.factories import ControlFactory, ConsentFactory, SchemeAccountFactory, \
    SchemeCredentialQuestionFactory, SchemeFactory, UserConsentFactory
from ubiquity.tests.factories import SchemeAccountEntryFactory
from user.tests.factories import UserFactory


class TestCreateSchemeAccountSerializer(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        request = MagicMock()
        request.user = cls.user
        cls.serializer = CreateSchemeAccountSerializer()
        cls.serializer.context['request'] = request

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


class TestAnswerValidation(GlobalMockAPITestCase):
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

    def test_temporary_iceland_fix_ignores_question_validation(self):
        scheme = SchemeFactory(slug='iceland-bonus-card')
        SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE, manual_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK)
        scheme_account = SchemeAccountFactory(scheme=scheme)
        context = {
            'scheme': scheme,
            'scheme_account': scheme_account
        }
        serializer = LinkSchemeSerializer(data={}, context=context)
        self.assertTrue(serializer.is_valid())

    def test_temporary_iceland_fix_doesnt_break_question_validation(self):
        scheme = SchemeFactory(slug='not-iceland')
        SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE, manual_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK)
        scheme_account = SchemeAccountFactory(scheme=scheme)
        context = {
            'scheme': scheme,
            'scheme_account': scheme_account
        }
        serializer = LinkSchemeSerializer(data={}, context=context)
        self.assertFalse(serializer.is_valid())


class TestSchemeSerializer(GlobalMockAPITestCase):
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


class TestUserConsentSerializer(GlobalMockAPITestCase):
    def setUp(self):
        self.scheme = SchemeFactory()

        self.consent1 = ConsentFactory(required=True, journey=JourneyTypes.LINK.value,
                                       check_box=True, scheme=self.scheme)
        self.consent2 = ConsentFactory(required=False, journey=JourneyTypes.LINK.value,
                                       check_box=True, scheme=self.scheme)
        self.consent3 = ConsentFactory(required=True, journey=JourneyTypes.JOIN.value,
                                       check_box=True, scheme=self.scheme)
        self.consent4 = ConsentFactory(required=True, journey=JourneyTypes.JOIN.value,
                                       check_box=True, scheme=self.scheme)
        self.consent5 = ConsentFactory(required=False, journey=JourneyTypes.JOIN.value,
                                       check_box=False, scheme=self.scheme)

        self.scheme_account = SchemeAccountFactory(scheme=self.scheme)
        self.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=self.scheme_account)
        self.user = self.scheme_account_entry.user

        self.user_consent1 = UserConsentFactory(scheme=self.scheme_account.scheme)
        self.user_consent2 = UserConsentFactory(scheme=self.scheme_account.scheme)
        self.user_consent3 = UserConsentFactory(scheme=self.scheme_account.scheme)

    def test_get_user_consents(self):
        consent_data = [
            {'id': self.consent1.id, 'value': True},  # link
            {'id': self.consent3.id, 'value': True},  # join
            {'id': self.consent4.id, 'value': True},  # join
        ]

        metadata_keys = ['id', 'check_box', 'text', 'required', 'order', 'journey', 'slug', 'user_email', 'scheme_slug']

        scheme_consents = Consent.objects.filter(
            scheme=self.scheme_account.scheme.id,
            journey=JourneyTypes.JOIN.value,
            check_box=True
        )

        user_consents = UserConsentSerializer.get_user_consents(
            self.scheme_account, consent_data, self.user, scheme_consents
        )

        self.assertEqual(len(user_consents), 2)
        self.assertTrue(all([metadata_keys == list(consent.metadata.keys()) for consent in user_consents]))

    def test_validate_consents_success(self):
        self.user_consent1.slug = self.consent1.slug
        self.user_consent1.metadata = {'id': self.consent1.id, 'required': self.consent1.required}

        self.user_consent2.slug = self.consent2.slug
        self.user_consent2.metadata = {'id': self.consent2.id, 'required': self.consent2.required}

        scheme_consents = Consent.objects.filter(
            scheme=self.scheme.id,
            journey=JourneyTypes.LINK.value,
            check_box=True
        )

        UserConsentSerializer.validate_consents(
            [self.user_consent1, self.user_consent2],
            self.scheme.id,
            JourneyTypes.LINK.value,
            scheme_consents
        )

    def test_validate_consents_raises_error_on_incorrect_number_of_consents_provided(self):
        scheme_consents = Consent.objects.filter(
            scheme=self.scheme.id,
            journey=JourneyTypes.LINK.value,
            check_box=True
        )

        with self.assertRaises(serializers.ValidationError) as e:
            UserConsentSerializer.validate_consents(
                [self.user_consent1, self.user_consent2, self.user_consent3],
                self.scheme.id,
                JourneyTypes.LINK.value,
                scheme_consents
            )

        self.assertEqual("Incorrect number of consents provided for this scheme and journey type.",
                         e.exception.detail['message'])

        with self.assertRaises(serializers.ValidationError) as e:
            UserConsentSerializer.validate_consents(
                [self.user_consent1],
                self.scheme.id,
                JourneyTypes.LINK.value,
                scheme_consents
            )

        self.assertEqual("Incorrect number of consents provided for this scheme and journey type.",
                         e.exception.detail['message'])

    def test_validate_consents_raises_error_on_unexpected_consent_slug(self):
        scheme_consents = Consent.objects.filter(
            scheme=self.scheme.id,
            journey=JourneyTypes.LINK.value,
            check_box=True
        )

        self.user_consent1.slug = 'incorrect_slug'
        with self.assertRaises(serializers.ValidationError) as e:
            UserConsentSerializer.validate_consents(
                [self.user_consent1, self.user_consent2],
                self.scheme.id,
                JourneyTypes.LINK.value,
                scheme_consents
            )

        self.assertTrue("Unexpected or missing user consents for 'link' request" in e.exception.detail['message'])

    def test_validate_consents_raises_error_on_required_consents_with_false_value(self):
        self.user_consent1.value = False
        self.user_consent1.slug = self.consent1.slug
        self.user_consent1.metadata = {'id': self.consent1.id, 'required': self.consent1.required}

        self.user_consent2.value = False
        self.user_consent2.slug = self.consent2.slug
        self.user_consent2.metadata = {'id': self.consent2.id, 'required': self.consent2.required}

        scheme_consents = Consent.objects.filter(
            scheme=self.scheme.id,
            journey=JourneyTypes.LINK.value,
            check_box=True
        )

        with self.assertRaises(serializers.ValidationError) as e:
            UserConsentSerializer.validate_consents(
                [self.user_consent1, self.user_consent2],
                self.scheme.id,
                JourneyTypes.LINK.value,
                scheme_consents
            )

        self.assertTrue("The following consents require a value of True:" in e.exception.detail['message'])
        self.assertTrue(
            "[{{'consent_id': {}, 'slug': '{}'}}]".format(self.consent1.id, self.consent1.slug)
            in str(e.exception.detail['message'])
        )


class TestJoinSerializer(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        scheme = SchemeFactory()
        cls.req_question = SchemeCredentialQuestionFactory(type=BARCODE, scheme=scheme,
                                                           options=SchemeCredentialQuestion.JOIN)
        cls.opt_request = SchemeCredentialQuestionFactory(type=LAST_NAME, scheme=scheme,
                                                          options=SchemeCredentialQuestion.OPTIONAL_JOIN)
        context = {
            'scheme': scheme,
            'user': '1'
        }
        cls.serializer = JoinSerializer(context=context)

    def test_missing_required_questions_raises_error(self):
        with self.assertRaises(ValidationError):
            self.serializer.validate({'last_name': 'test'})

    def test_missing_optional_questions_doesnt_raises_error(self):
        data = self.serializer.validate({'barcode': '123'})
        self.assertIn('barcode', data['credentials'])

    def test_optional_credentials_get_sent(self):
        data = self.serializer.validate({'barcode': '123', 'last_name': 'test'})
        self.assertIn('barcode', data['credentials'])
        self.assertIn('last_name', data['credentials'])


class TestUpdateUserConsentSerializer(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.serializer_class = UpdateUserConsentSerializer

    def test_only_valid_fields_are_accepted(self):
        # Valid / fields that can be updated
        status = 'status'

        # Should not be updated
        value = 'value'

        serializer = self.serializer_class(data={status: 1, value: False})
        serializer.is_valid()
        validated_data = serializer.validated_data

        self.assertIn(status, serializer.validated_data)
        self.assertNotIn(value, validated_data)

    def test_is_valid_returns_false_on_invalid_status(self):
        serializer = self.serializer_class(data={'status': 102312132})

        self.assertFalse(serializer.is_valid())

    def test_is_valid_returns_false_on_updating_existing_success_status(self):
        user_consent = UserConsentFactory(status=ConsentStatus.SUCCESS)
        serializer = self.serializer_class(user_consent, data={'status': 0})

        self.assertFalse(serializer.is_valid())


class TestControlSerializer(GlobalMockAPITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.scheme = SchemeFactory()

        cls.control = ControlFactory(scheme=cls.scheme, key=Control.JOIN_KEY)

        cls.serializer_class = ControlSerializer

    def test_correct_control_representation(self):
        serializer = self.serializer_class(self.control)

        keys = ['key', 'label', 'hint_text']

        self.assertEqual(len(serializer.data.keys()), 3)
        for key in keys:
            self.assertIn(key, serializer.data)

        self.assertEqual(serializer.data['key'], 'join_button')

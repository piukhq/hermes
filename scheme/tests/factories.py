from datetime import datetime

import factory
from django.utils import timezone
from factory.fuzzy import FuzzyAttribute

from scheme import models
from scheme.models import Control
from faker import Factory
from scheme.credentials import USER_NAME
from scheme.models import Consent, ConsentStatus, JourneyTypes, UserConsent
from user.tests.factories import UserFactory, ClientApplicationBundleFactory

fake = Factory.create()
# Change seed value if we start getting duplicate data
fake.seed(123456)


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Category

    name = fake.safe_color_name()


class SchemeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Scheme
        django_get_or_create = ('slug',)

    name = FuzzyAttribute(fake.company)
    slug = FuzzyAttribute(fake.slug)
    url = fake.url()
    transaction_headers = ["header 1", "header 2", "header 3"]
    company = fake.company()
    company_url = fake.url()
    forgotten_password_url = fake.url()
    tier = 1
    has_transactions = True
    has_points = True
    barcode_type = 1
    scan_message = fake.sentence()
    category = factory.SubFactory(CategoryFactory)
    identifier = ''
    card_number_regex = ''
    barcode_prefix = ''


class SchemeBalanceDetailsFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.SchemeBalanceDetails

    scheme_id = factory.SubFactory(SchemeFactory)
    currency = fake.company()
    suffix = fake.slug()


class ConsentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Consent

    text = fake.sentence()
    scheme = factory.SubFactory(SchemeFactory)
    check_box = True
    is_enabled = True
    required = True
    order = 1
    journey = JourneyTypes.LINK.value
    slug = FuzzyAttribute(fake.slug)


KEY_CHOICES = [x[0] for x in Control.KEY_CHOICES]


class ControlFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Control

    key = factory.fuzzy.FuzzyChoice(KEY_CHOICES)
    label = fake.sentence(nb_words=3)
    hint_text = fake.sentence(nb_words=10)

    scheme = factory.SubFactory(SchemeFactory)


class SchemeBundleAssociationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.SchemeBundleAssociation

    scheme = factory.SubFactory(SchemeFactory)
    bundle = factory.SubFactory(ClientApplicationBundleFactory)
    status = models.SchemeBundleAssociation.ACTIVE


class SchemeAccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.SchemeAccount

    scheme = factory.SubFactory(SchemeFactory)
    status = models.SchemeAccount.ACTIVE
    order = 0
    vouchers = [
        {
            "burn": {
                "type": "voucher",
                "value": 2.5,
                "prefix": "\u00a3",
                "suffix": "Reward",
                "currency": ""
            },
            "code": "WHS000052",
            "earn": {
                "type": "stamps",
                "value": 5.0,
                "prefix": "",
                "suffix": "stamps",
                "currency": "",
                "target_value": 5.0
            },
            "state": "issued",
            "subtext": "",
            "headline": "Earned",
            "body_text": "",
            "date_issued": 1600560000,
            "expiry_date": 1609459200,
            "barcode_type": 0,
            "terms_and_conditions_url": ""
        },
        {
            "burn": {
                "type": "voucher",
                "value": 2.5,
                "prefix": "\u00a3",
                "suffix": "Reward",
                "currency": ""
            },
            "code": 'WHS000053',
            "earn": {
                "type": "stamps",
                "value": 5.0,
                "prefix": "",
                "suffix": "stamps",
                "currency": "",
                "target_value": 5.0
            },
            "state": "expired",
            "subtext": "",
            "headline": "Expired",
            "body_text": "",
            "date_issued": 1600560000,
            "expiry_date": 1596240000,
            "barcode_type": 0,
            "terms_and_conditions_url": ""
        },
        {
            "burn": {
                "type": "voucher",
                "value": 2.5,
                "prefix": "\u00a3",
                "suffix": "Reward",
                "currency": ""
            },
            "code": 'WHS000054',
            "earn": {
                "type": "stamps",
                "value": 5.0,
                "prefix": "",
                "suffix": "stamps",
                "currency": "",
                "target_value": 5.0
            },
            "state": "redeemed",
            "subtext": "",
            "headline": "Redeemed",
            "body_text": "",
            "date_issued": 1600560000,
            "expiry_date": 1596499200,
            "barcode_type": 0,
            "date_redeemed": 1600646400,
            "terms_and_conditions_url": ""
        },
    ]


class UserConsentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserConsent

    user = factory.SubFactory(UserFactory)
    slug = FuzzyAttribute(fake.slug)
    scheme = factory.SubFactory(SchemeFactory)
    scheme_account = factory.SubFactory(SchemeAccountFactory)
    value = True
    metadata = ''
    status = ConsentStatus.PENDING


class SchemeCredentialQuestionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.SchemeCredentialQuestion

    scheme = factory.SubFactory(SchemeFactory)
    type = USER_NAME
    label = 'Please enter your username.'
    third_party_identifier = False


class SchemeCredentialAnswerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.SchemeAccountCredentialAnswer

    scheme_account = factory.SubFactory(SchemeAccountFactory)
    question = factory.SubFactory(SchemeCredentialQuestionFactory)
    answer = fake.first_name()


class SchemeImageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.SchemeImage

    scheme = factory.SubFactory(SchemeFactory)
    image_type_code = 1
    size_code = fake.word()
    image = fake.url()
    strap_line = fake.sentence(nb_words=3)[:Meta.model._meta.get_field('strap_line').max_length - 1]
    description = fake.sentence(nb_words=3)
    url = fake.url()
    call_to_action = fake.sentence(nb_words=3)
    order = 0
    status = 1
    start_date = timezone.now()
    end_date = timezone.make_aware(datetime(2200, 1, 1))


class SchemeAccountImageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.SchemeAccountImage

    image_type_code = 1
    size_code = fake.word()
    image = fake.url()

    strap_line = fake.sentence(nb_words=3)
    description = fake.sentence(nb_words=3)
    url = fake.url()
    call_to_action = fake.sentence(nb_words=3)
    reward_tier = 0

    order = 0

    status = 1

    scheme = factory.SubFactory(SchemeFactory)

    start_date = timezone.now()
    end_date = timezone.now() + timezone.timedelta(days=1)


class ExchangeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Exchange

    exchange_rate_donor = 1
    exchange_rate_host = 1

    transfer_min = 0
    transfer_max = 1000
    transfer_multiple = 100

    tip_in_url = fake.url()
    info_url = fake.url()

    flag_auto_tip_in = 0


class SchemeCredentialQuestionChoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.SchemeCredentialQuestionChoice

    scheme = factory.SubFactory(SchemeFactory)
    scheme_question = factory.SubFactory(SchemeCredentialQuestionFactory)


class SchemeCredentialQuestionChoiceValueFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.SchemeCredentialQuestionChoiceValue

    choice = factory.SubFactory(SchemeCredentialQuestionChoiceFactory)
    value = fake.slug()

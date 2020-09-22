import typing as t
from decimal import Decimal, ROUND_HALF_UP
from os.path import join

import arrow
import jwt
import requests
from arrow.parser import ParserError
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty
from rest_framework.serializers import as_serializer_error
from shared_config_storage.ubiquity.bin_lookup import bin_to_provider

from common.models import check_active_image
from payment_card.models import Issuer, PaymentCard, PaymentCardAccount
from payment_card.serializers import CreatePaymentCardAccountSerializer
from scheme.credentials import credential_types_set
from scheme.models import (Scheme, SchemeBalanceDetails, SchemeCredentialQuestion, SchemeDetail, ThirdPartyConsentLink,
                           VoucherScheme)
from scheme.serializers import JoinSerializer, UserConsentSerializer, SchemeAnswerSerializer
from ubiquity.models import PaymentCardSchemeEntry, ServiceConsent, MembershipPlanDocument
from ubiquity.reason_codes import reason_code_translation, ubiquity_status_translation
from ubiquity.tasks import async_balance

if t.TYPE_CHECKING:
    from scheme.models import SchemeAccount


def _add_base_media_url(image: dict) -> dict:
    if settings.NO_AZURE_STORAGE:
        base_url = settings.MEDIA_URL
    else:
        base_url = settings.AZURE_CUSTOM_DOMAIN

    return {
        **image,
        'url': join(base_url, image['url'])
    }


class MembershipTransactionsMixin:

    @staticmethod
    def _get_auth_token(user_id):
        payload = {
            'sub': user_id
        }
        token = jwt.encode(payload, settings.TOKEN_SECRET)
        return 'token {}'.format(token.decode('unicode_escape'))

    def _get_hades_transactions(self, user_id, mcard_id):
        url = '{}/transactions/scheme_account/{}?page_size=5'.format(settings.HADES_URL, mcard_id)
        headers = {'Authorization': self._get_auth_token(user_id), 'Content-Type': 'application/json'}
        resp = requests.get(url, headers=headers)
        return resp.json() if resp.status_code == 200 else []

    def get_transactions_id(self, user_id, mcard_id):
        return [tx['id'] for tx in self._get_hades_transactions(user_id, mcard_id)]

    def get_transactions_data(self, user_id, mcard_id):
        resp = self._get_hades_transactions(user_id, mcard_id)
        return resp if resp else []


class ServiceConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceConsent
        fields = '__all__'
        write_only_fields = ('user',)

    timestamp = serializers.IntegerField()

    @staticmethod
    def validate_timestamp(timestamp):
        try:
            datetime = arrow.get(timestamp).datetime
        except ParserError:
            raise serializers.ValidationError('timestamp field is not a timestamp.')

        return datetime

    @staticmethod
    def _is_valid(value):
        if value or isinstance(value, (int, float)):
            return True
        return False

    def to_representation(self, instance):
        response = {'email': instance.user.email, 'timestamp': int(instance.timestamp.timestamp())}
        if self._is_valid(instance.latitude) and self._is_valid(instance.longitude):
            response.update({'latitude': instance.latitude, 'longitude': instance.longitude})
        return {
            'consent': response
        }


class PaymentCardConsentSerializer(serializers.Serializer):
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)
    timestamp = serializers.IntegerField(required=True)
    type = serializers.IntegerField(required=True)

    @staticmethod
    def validate_timestamp(timestamp):
        try:
            date = arrow.get(timestamp)
        except ParserError:
            raise serializers.ValidationError('timestamp field is not a timestamp.')

        return date.timestamp


class UbiquityImageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.IntegerField(source='image_type_code')
    url = serializers.ImageField(source='image')
    description = serializers.CharField()
    encoding = serializers.SerializerMethodField()

    @staticmethod
    def get_encoding(obj):
        if obj.encoding:
            return obj.encoding

        try:
            return obj.image.name.split('.')[-1].replace('/', '')
        except (IndexError, AttributeError):
            return None


class PaymentCardSerializer:
    def __init__(self, data, many=False, context=None):
        self.context = context or {}
        if many:
            self.formatted_data = [self.to_representation(instance) for instance in data]
        else:
            self.formatted_data = self.to_representation(data)

    @property
    def data(self):
        return self.formatted_data

    @staticmethod
    def _get_images(instance: PaymentCardAccount):
        today = arrow.utcnow().datetime.timestamp()
        account_images = {
            image_type: image['payload']
            for image_type, images in instance.formatted_images.items()
            for image in images.values()
            if image and check_active_image(image.get('validity', {}), today)
        }

        base_images = {
            image_type: image['payload']
            for image_type, images in instance.payment_card.formatted_images.items()
            for image in images.values()
            if image and check_active_image(image.get('validity', {}), today)
        }

        return [
            _add_base_media_url(account_images.get(image_type, image))
            for image_type, image in base_images.items()
        ]

    def to_representation(self, instance):
        status = 'active' if instance.status == PaymentCardAccount.ACTIVE else 'pending'
        return {
            "id": instance.id,
            "membership_cards": instance.pll_links,
            "status": status,
            "card": {
                "first_six_digits": str(instance.pan_start),
                "last_four_digits": str(instance.pan_end),
                "month": int(instance.expiry_month),
                "year": int(instance.expiry_year),
                "country": instance.country,
                "currency_code": instance.currency_code,
                "name_on_card": instance.name_on_card,
                "provider": instance.payment_card.system_name,
                "type": instance.payment_card.type
            },
            "images": self._get_images(instance),
            "account": {
                "verification_in_progress": False,
                "status": 1,
                "consents": instance.consents
            }
        }


class PaymentCardTranslationSerializer:
    def __init__(self, data, context=None):
        self.context = context or {}
        self.formatted_data = self.to_representation(data)

    @staticmethod
    def get_issuer(_):
        return Issuer.get_barclays_issuer()

    @staticmethod
    def get_payment_card(obj):
        slug = bin_to_provider(str(obj['first_six_digits']))
        return PaymentCard.get_by_slug(slug)

    def to_representation(self, data):
        return {
            'pan_start': data['first_six_digits'],
            'pan_end': data['last_four_digits'],
            'issuer': self.get_issuer(data),
            'payment_card': self.get_payment_card(data),
            'name_on_card': data['name_on_card'],
            'token': data['token'],
            'fingerprint': data['fingerprint'],
            'expiry_year': int(data['year']),
            'expiry_month': int(data['month']),
            'country': data.get('country', 'UK'),
            'order': int(data.get('order', '0')),
            'currency_code': data.get('currency_code', 'GBP')
        }

    @property
    def data(self):
        return self.formatted_data


class PaymentCardUpdateSerializer(serializers.Serializer):
    pan_start = serializers.CharField(source='first_six_digits', required=False)
    pan_end = serializers.CharField(source='last_four_digits', required=False)
    issuer = serializers.IntegerField(required=False)
    payment_card = serializers.IntegerField(required=False)
    name_on_card = serializers.CharField(required=False)
    token = serializers.CharField(required=False)
    fingerprint = serializers.CharField(required=False)
    expiry_year = serializers.IntegerField(source='year', required=False)
    expiry_month = serializers.IntegerField(source='month', required=False)
    country = serializers.CharField(required=False)
    order = serializers.IntegerField(required=False, default=0)
    currency_code = serializers.CharField(required=False, default='GBP')


class TransactionListSerializer(serializers.ListSerializer):
    def run_validation(self, data=empty):
        """
        Overriding run_validation in order to filter transactions for the given user before
        converting the data to the internal value. This would usually be done in .validate()
        but cannot be in this case since the internal value does not store the scheme_account_id,
        which is required for the filtering.
        """
        (is_empty_value, data) = self.validate_empty_values(data)
        if is_empty_value:
            return data

        if self.context.get("user"):
            data = self.filter_transactions_for_user(data)
        value = self.to_internal_value(data)
        try:
            self.run_validators(value)
            value = self.validate(value)
            assert value is not None, '.validate() should return the validated data'
        except (ValidationError, DjangoValidationError) as exc:
            raise ValidationError(detail=as_serializer_error(exc))

        return value

    def filter_transactions_for_user(self, data):
        user = self.context["user"]
        queryset = user.scheme_account_set.values('id')
        if not user.is_tester:
            queryset = queryset.filter(scheme__test_scheme=False).values('id').all()

        return [
            tx for tx in data
            if tx.get('scheme_account_id') in {account['id'] for account in queryset.all()}
        ]


class TransactionSerializer(serializers.Serializer):
    """
    A second version of the TransactionsSerializer since the original does not
    validate input fields when deserializing.
    """
    scheme_info = None
    status = "active"
    id = serializers.IntegerField()
    scheme_account_id = serializers.IntegerField()
    date = serializers.DateTimeField()
    description = serializers.CharField()
    points = serializers.FloatField()

    class Meta:
        list_serializer_class = TransactionListSerializer

    def to_representation(self, instance):
        return {
            "id": instance["id"],
            "status": self.status,
            "timestamp": instance.get("timestamp") or arrow.get(instance["date"]).timestamp,
            "description": instance["description"],
            "amounts": instance.get("amounts") or self.get_amounts(instance),
        }

    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        return {
            "id": data["id"],
            "status": self.status,
            "timestamp": arrow.get(data["date"]).timestamp,
            "description": data["description"],
            "amounts": self.get_amounts(data)
        }

    def _get_scheme_info(self, mcard_id):
        if self.scheme_info:
            return self.scheme_info

        self.scheme_info = Scheme.objects.get(schemeaccount__id=mcard_id).schemebalancedetails_set.first()
        return self.scheme_info

    def get_amounts(self, instance):
        scheme_balances = self._get_scheme_info(instance['scheme_account_id'])
        amounts = []

        if scheme_balances.currency in ['GBP', 'EUR', 'USD']:
            amounts.append(
                {
                    'currency': scheme_balances.currency,
                    'prefix': scheme_balances.prefix,
                    'suffix': scheme_balances.suffix,
                    'value': float(Decimal(instance['points']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
                }
            )
        else:
            amounts.append(
                {
                    'currency': scheme_balances.currency,
                    'prefix': scheme_balances.prefix,
                    'suffix': scheme_balances.suffix,
                    'value': int(instance['points'])
                }
            )

        return amounts


class ActiveCardAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCardSchemeEntry
        fields = ()


class SchemeQuestionSerializer(serializers.ModelSerializer):
    column = serializers.CharField(source='label')
    common_name = serializers.CharField(source='type')
    type = serializers.IntegerField(source='answer_type')

    class Meta:
        model = SchemeCredentialQuestion
        fields = ('column', 'validation', 'description', 'common_name', 'type', 'choice')


class SchemeDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeDetail
        fields = ('name', 'description')


class SchemeBalanceDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeBalanceDetails
        exclude = ('scheme_id', 'id')


class MembershipPlanDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipPlanDocument
        exclude = ('id', 'scheme')


class UbiquityConsentSerializer(serializers.Serializer):
    column = serializers.CharField(source='consent_label')
    description = serializers.CharField(source='consent.text')

    class Meta:
        model = ThirdPartyConsentLink
        fields = ('consent_label', 'consent',)

    def to_representation(self, obj):
        data = super().to_representation(obj)
        data['type'] = SchemeCredentialQuestion.ANSWER_TYPE_CHOICES[3][0]  # boolean
        return data


class MembershipPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scheme
        exclude = ('name',)

    @staticmethod
    def _add_alternatives_key(formatted_fields: dict) -> None:
        options = {field["column"] for field in formatted_fields}
        for field in formatted_fields:
            field["alternatives"] = list(options - {field["column"]})

    def _format_add_fields(self, fields: SchemeCredentialQuestion) -> list:
        formatted_fields = SchemeQuestionSerializer(fields, many=True).data
        if len(formatted_fields) > 1:
            self._add_alternatives_key(formatted_fields)

        return formatted_fields

    def _get_scheme_consents(self, scheme):
        try:
            client = self.context['request'].user.client
        except KeyError as e:
            raise RuntimeError('Missing request object in context for retrieving client app information') from e

        all_consents = ThirdPartyConsentLink.objects.filter(
            client_app=client,
            scheme=scheme
        ).all()

        consents = {
            'add': [consent for consent in all_consents if consent.add_field is True],
            'authorise': [consent for consent in all_consents if consent.auth_field is True],
            'register': [consent for consent in all_consents if consent.register_field is True],
            'enrol': [consent for consent in all_consents if consent.enrol_field is True]
        }

        return consents

    def to_representation(self, instance: Scheme) -> dict:
        images = instance.images.all()
        balances = instance.schemebalancedetails_set.all()
        tiers = instance.schemedetail_set.filter(type=0).all()
        add_fields = instance.questions.filter(add_field=True).all()
        authorise_fields = instance.questions.filter(auth_field=True).all()
        registration_fields = instance.questions.filter(register_field=True).all()
        enrol_fields = instance.questions.filter(enrol_field=True).all()
        # To get here status must be active (i.e. suspended currently maps to inactive)
        # if changed for real status is required call channels_permit.scheme_status_name(instance.id)
        status = 'active'
        documents = instance.documents.all()
        consents = self._get_scheme_consents(scheme=instance)

        if instance.tier == 1:
            card_type = 2
        elif instance.has_points or instance.has_transactions:
            card_type = 1
        else:
            card_type = 0

        plan = {
            'id': instance.id,
            'status': status,
            'feature_set': {
                'authorisation_required': instance.authorisation_required,
                'transactions_available': instance.has_transactions,
                'digital_only': instance.digital_only,
                'has_points': instance.has_points,
                'card_type': card_type,
                'linking_support': instance.linking_support,
                'apps': [
                    {
                        'app_id': instance.ios_scheme,
                        'app_store_url': instance.itunes_url,
                        'app_type': 0
                    },
                    {
                        'app_id': instance.android_app_id,
                        'app_store_url': instance.play_store_url,
                        'app_type': 1
                    }
                ]
            },
            'card': {
                'barcode_type': instance.barcode_type,
                'colour': instance.colour,
                'base64_image': '',
                'scan_message': instance.scan_message
            },
            'images': UbiquityImageSerializer(images, many=True).data,
            'account': {
                'plan_name': instance.name,
                'plan_name_card': instance.plan_name_card,
                'plan_url': instance.url,
                'plan_summary': instance.plan_summary,
                'plan_description': instance.plan_description,
                'plan_documents': MembershipPlanDocumentSerializer(documents, many=True).data,
                'barcode_redeem_instructions': instance.barcode_redeem_instructions,
                'plan_register_info': instance.plan_register_info,
                'company_name': instance.company,
                'company_url': instance.company_url,
                'enrol_incentive': instance.enrol_incentive,
                'category': instance.category.name,
                'forgotten_password_url': instance.forgotten_password_url,
                'tiers': SchemeDetailSerializer(tiers, many=True).data,
                'add_fields': (self._format_add_fields(add_fields) +
                               UbiquityConsentSerializer(consents['add'], many=True).data),
                'authorise_fields': (SchemeQuestionSerializer(authorise_fields, many=True).data +
                                     UbiquityConsentSerializer(consents['authorise'], many=True).data),
                'registration_fields': (SchemeQuestionSerializer(registration_fields, many=True).data +
                                        UbiquityConsentSerializer(consents['register'], many=True).data),
                'enrol_fields': (SchemeQuestionSerializer(enrol_fields, many=True).data +
                                 UbiquityConsentSerializer(consents['enrol'], many=True).data),
            },
            'balances': SchemeBalanceDetailSerializer(balances, many=True).data,
        }

        if VoucherScheme.objects.filter(scheme_id=instance.id).exists():
            plan['has_vouchers'] = True

        return plan


class MembershipCardSerializer(serializers.Serializer, MembershipTransactionsMixin):

    @staticmethod
    def _filter_valid_images(account_images: dict, base_images: dict, today: int) -> t.ValuesView[t.Dict[str, dict]]:
        images = {}
        for image_type in ['images', 'tier_images']:
            valid_account_images = {
                image_type: image['payload']
                for image_type, images in account_images.get(image_type, {}).items()
                for image in images.values()
                if image and check_active_image(image.get('validity', {}), today)
            }
            valid_base_images = {
                image_type: image['payload']
                for image_type, images in base_images.get(image_type, {}).items()
                for image in images.values()
                if image and check_active_image(image.get('validity', {}), today)
            }
            images[image_type] = {
                'valid_account_images': valid_account_images,
                'valid_base_images': valid_base_images
            }

        return images.values()

    def _get_images(self, instance: 'SchemeAccount', scheme: 'Scheme', tier: str) -> list:
        today = arrow.utcnow().datetime.timestamp()
        account_images = instance.formatted_images
        base_images = scheme.formatted_images
        images, tier_images = self._filter_valid_images(account_images, base_images, today)

        filtered_images = [
            _add_base_media_url(images['valid_account_images'].get(image_type, base_image))
            for image_type, base_image in images['valid_base_images'].items()
        ]

        tier_image = (tier_images['valid_account_images'].get(tier, None) or
                      tier_images['valid_base_images'].get(tier, None))
        if tier_image:
            filtered_images.append(_add_base_media_url(tier_image))

        return filtered_images

    @staticmethod
    def get_translated_status(instance: 'SchemeAccount') -> dict:
        status = instance.status
        if status in instance.SYSTEM_ACTION_REQUIRED:
            if instance.balances:
                status = instance.ACTIVE
            else:
                status = instance.PENDING

        return {
            'state': ubiquity_status_translation[status],
            'reason_codes': [
                reason_code_translation[code] for code in [status]
                if reason_code_translation[code] is not None
            ]
        }

    @staticmethod
    def _strip_reward_tier(balances):
        return [
            {
                k: v
                for k, v in balance.items()
                if k != 'reward_tier'
            }
            for balance in balances
        ]

    def to_representation(self, instance: 'SchemeAccount') -> dict:
        if instance.status not in instance.EXCLUDE_BALANCE_STATUSES:
            async_balance.delay(instance.id)
        try:
            reward_tier = instance.balances[0]['reward_tier']
        except (ValueError, KeyError):
            reward_tier = 0

        try:
            current_scheme = self.context['view'].current_scheme
        except (KeyError, AttributeError):
            current_scheme = None

        scheme = current_scheme if current_scheme is not None else instance.scheme
        card_repr = {
            'id': instance.id,
            'membership_plan': instance.scheme_id,
            'payment_cards': instance.pll_links,
            'membership_transactions': instance.transactions,
            'status': self.get_translated_status(instance),
            'card': {
                'barcode': instance.barcode,
                'membership_id': instance.card_number,
                'barcode_type': scheme.barcode_type,
                'colour': scheme.colour
            },
            'images': self._get_images(instance, scheme, str(reward_tier)),
            'account': {
                'tier': reward_tier
            },
            'balances': self._strip_reward_tier(instance.balances)
        }

        if instance.vouchers is not None:
            vouchers = instance.vouchers
            for voucher in instance.vouchers:
                if voucher.get('code'):
                    if voucher['state'] in ['expired', 'redeemed']:
                        voucher['code'] = None
                else:
                    continue
            card_repr["vouchers"] = vouchers

        return card_repr


class LinkMembershipCardSerializer(SchemeAnswerSerializer):
    scheme = serializers.IntegerField()
    order = serializers.IntegerField()
    id = serializers.IntegerField(read_only=True)
    consents = UserConsentSerializer(many=True, write_only=True, required=False)

    def validate(self, data):
        scheme = self.context['view'].current_scheme
        scheme_questions = self.context['view'].scheme_questions
        if not scheme:
            scheme = Scheme.get_scheme_and_questions_by_scheme_id(data['scheme'])

        if scheme.id != data['scheme']:
            raise serializers.ValidationError("wrong scheme id")

        answer_types = set(data).intersection(credential_types_set)
        if len(answer_types) != 1:
            raise serializers.ValidationError("You must submit one scan or manual question answer")

        answer_type = answer_types.pop()
        self.context['answer_type'] = answer_type
        # only allow one credential
        if answer_type not in self.allowed_answers(scheme, scheme_questions):
            raise serializers.ValidationError("Your answer type '{0}' is not allowed".format(answer_type))

        return data

    @staticmethod
    def allowed_answers(scheme, scheme_questions):
        if scheme_questions:
            return [
                question.type
                for question in scheme_questions
                if any(map(
                    lambda question_type: getattr(question, question_type),
                    ['manual_question', 'scan_question', 'one_question_link']
                ))
            ]
        else:
            return [
                question['type']
                for question in scheme.get_required_questions(scheme_questions)
            ]


# todo adapt or remove
class JoinMembershipCardSerializer(JoinSerializer):
    pass


class PaymentCardReplaceSerializer(CreatePaymentCardAccountSerializer):
    token = serializers.CharField(max_length=255, write_only=True, source='psp_token')

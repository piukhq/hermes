import typing as t
from decimal import Decimal, ROUND_HALF_UP

import arrow
import jwt
from arrow.parser import ParserError
from django.conf import settings
from rest_framework import serializers

from hermes.traced_requests import requests
from payment_card.models import Issuer, PaymentCard
from payment_card.serializers import (CreatePaymentCardAccountSerializer, PaymentCardAccountSerializer,
                                      get_images_for_payment_card_account)
from scheme.models import Scheme, SchemeBalanceDetails, SchemeCredentialQuestion, SchemeDetail, ThirdPartyConsentLink
from scheme.serializers import CreateSchemeAccountSerializer, JoinSerializer
from ubiquity.models import PaymentCardSchemeEntry, ServiceConsent, MembershipPlanDocument
from ubiquity.reason_codes import reason_code_translation, ubiquity_status_translation
from ubiquity.tasks import async_balance
from user.models import CustomUser

if t.TYPE_CHECKING:
    from scheme.models import SchemeAccount


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
        return TransactionsSerializer(resp, many=True).data if resp else []


class ServiceConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceConsent
        fields = '__all__'
        write_only_fields = ('user',)

    timestamp = serializers.IntegerField()

    @staticmethod
    def validate_user(user):
        if not isinstance(user, CustomUser):
            try:
                user = CustomUser.objects.get(pk=user)
            except CustomUser.DoesNotExist:
                raise serializers.ValidationError("User {} not found.".format(user))

        return user

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


class PaymentCardSchemeEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCardSchemeEntry
        fields = '__all__'


class PaymentCardLinksSerializer(PaymentCardSchemeEntrySerializer):
    id = serializers.SerializerMethodField()

    @staticmethod
    def get_id(obj):
        return obj.payment_card_account_id

    class Meta:
        model = PaymentCardSchemeEntrySerializer.Meta.model
        exclude = ('payment_card_account', 'scheme_account')


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


class PaymentCardSerializer(PaymentCardAccountSerializer):
    membership_cards = serializers.SerializerMethodField()
    first_six_digits = serializers.CharField(source='pan_start')
    last_four_digits = serializers.CharField(source='pan_end')
    year = serializers.IntegerField(source='expiry_year')
    month = serializers.IntegerField(source='expiry_month')
    token = None

    @staticmethod
    def get_membership_cards(obj):
        query = {
            'payment_card_account': obj,
            'scheme_account__is_deleted': False
        }
        links = PaymentCardSchemeEntry.objects.filter(**query).all()
        return MembershipCardLinksSerializer(links, many=True).data

    class Meta(PaymentCardAccountSerializer.Meta):
        exclude = ('psp_token', 'user_set', 'scheme_account_set')
        read_only_fields = PaymentCardAccountSerializer.Meta.read_only_fields + ('membership_cards',)

    @staticmethod
    def _get_images(instance):
        return get_images_for_payment_card_account(instance, serializer_class=UbiquityImageSerializer,
                                                   add_type=False)

    def to_representation(self, instance):
        status = 'active' if instance.consents else 'pending'
        return {
            "id": instance.id,
            "membership_cards": self.get_membership_cards(instance),
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


# not used for now but will be needed
# class ListPaymentCardSerializer(PaymentCardSerializer):
#     @staticmethod
#     def _get_images(instance):
#         payment_card_images = PaymentCardImage.objects.filter(payment_card=instance.payment_card)
#         return [image.id for image in payment_card_images]


class PaymentCardTranslationSerializer(serializers.Serializer):
    pan_start = serializers.CharField(source='first_six_digits')
    pan_end = serializers.CharField(source='last_four_digits')
    issuer = serializers.SerializerMethodField()
    payment_card = serializers.SerializerMethodField()
    name_on_card = serializers.CharField()
    token = serializers.CharField()
    fingerprint = serializers.CharField()
    expiry_year = serializers.IntegerField(source='year')
    expiry_month = serializers.IntegerField(source='month')
    country = serializers.CharField(required=False, default='UK')
    order = serializers.IntegerField(required=False, default=0)
    currency_code = serializers.CharField(required=False, default='GBP')

    @staticmethod
    def get_issuer(_):
        return Issuer.objects.values('id').get(name='Barclays')['id']

    @staticmethod
    def get_payment_card(_):
        return PaymentCard.objects.values('id').get(slug='visa')['id']


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


class MembershipCardLinksSerializer(PaymentCardSchemeEntrySerializer):
    id = serializers.SerializerMethodField()

    @staticmethod
    def get_id(obj):
        return obj.scheme_account_id

    class Meta:
        model = PaymentCardSchemeEntrySerializer.Meta.model
        exclude = ('scheme_account', 'payment_card_account')


class TransactionsSerializer(serializers.Serializer):
    scheme_info = None
    id = serializers.IntegerField()
    status = serializers.SerializerMethodField()
    timestamp = serializers.SerializerMethodField()
    description = serializers.CharField()
    amounts = serializers.SerializerMethodField()

    @staticmethod
    def get_status(_):
        return 'active'

    @staticmethod
    def get_timestamp(instance):
        return arrow.get(instance['date']).timestamp

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
        data['type'] = SchemeCredentialQuestion.ANSWER_TYPE_CHOICES[3][0]    # boolean
        return data


class MembershipPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scheme
        exclude = ('name',)

    @staticmethod
    def _get_ubiquity_images(instance: Scheme) -> t.List[dict]:
        # by using a dictionary duplicates are overwritten (if two hero are present only one will be returned)
        filtered_images = {
            image.image_type_code: image
            for image in instance.images.all()
            if image.image_type_code in [image.HERO, image.ICON]
        }

        return UbiquityImageSerializer(list(filtered_images.values()), many=True).data

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
        balances = instance.schemebalancedetails_set.all()
        tiers = instance.schemedetail_set.filter(type=0).all()
        add_fields = instance.questions.filter(add_field=True).all()
        authorise_fields = instance.questions.filter(auth_field=True).all()
        registration_fields = instance.questions.filter(register_field=True).all()
        enrol_fields = instance.questions.filter(enrol_field=True).all()
        status = 'active' if instance.is_active else 'suspended'
        documents = instance.documents.all()
        consents = self._get_scheme_consents(scheme=instance)

        if instance.tier == 2:
            card_type = 2
        elif instance.has_points or instance.has_transactions:
            card_type = 1
        else:
            card_type = 0

        # todo remove this horrible patch as soon as Barclays uses the right field in their app.
        company_name = instance.company
        plan_name_card = instance.plan_name_card
        if 'harvey-nichols' in instance.slug:
            company_name = 'Rewards'
            plan_name_card = 'by Harvey Nichols'
        # ------------------------- end of horrible patch ------------------------------------ #

        return {
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
            'images': self._get_ubiquity_images(instance),
            'account': {
                'plan_name': instance.name,
                'plan_name_card': plan_name_card,
                'plan_url': instance.url,
                'plan_summary': instance.plan_summary,
                'plan_description': instance.plan_description,
                'plan_documents': MembershipPlanDocumentSerializer(documents, many=True).data,
                'barcode_redeem_instructions': instance.barcode_redeem_instructions,
                'plan_register_info': instance.plan_register_info,
                'company_name': company_name,
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
            'balances': SchemeBalanceDetailSerializer(balances, many=True).data
        }


# not used for now but will be needed
# class ListMembershipPlanSerializer(MembershipPlanSerializer):
#     @staticmethod
#     def _get_ubiquity_images(instance):
#         return [
#             image.id
#             for image in instance.images.all()
#             if image.image_type_code in [image.HERO, image.ICON]
#         ]


class UbiquityBalanceHandler:
    point_info = None
    value_info = None
    data = None
    precision = None

    def __init__(self, dictionary, many=False):
        if many:
            dictionary, *_ = dictionary

        if 'scheme_id' in dictionary:
            self._collect_scheme_balances_info(dictionary['scheme_id'])

        self.point_balance = dictionary.get('points')
        self.value_balance = dictionary.get('value')
        self.updated_at = dictionary.get('updated_at')
        self._get_balances()

    def _collect_scheme_balances_info(self, scheme_id):
        for balance_info in SchemeBalanceDetails.objects.filter(scheme_id=scheme_id).all():
            # Set info for points or known currencies and also set precision for each supported currency
            if balance_info.currency in ['GBP', 'EUR', 'USD']:
                self.value_info = balance_info
                self.precision = Decimal('0.01')
            else:
                self.point_info = balance_info

    def _format_balance(self, value, info, is_currency):
        """
        :param value:
        :type value: float, int, string or Decimal
        :param info:
        :type info: SchemeBalanceDetails
        :return: dict
        """
        # The spec requires currency to be returned as a float this is done at final format since any
        # subsequent arithmetic function would cause a rounding error.
        if is_currency and self.precision is not None:
            value = float(Decimal(value).quantize(self.precision, rounding=ROUND_HALF_UP))
        else:
            value = int(value)

        return {
            "value": value,
            "currency": info.currency,
            "prefix": info.prefix,
            "suffix": info.suffix,
            "description": info.description,
            "updated_at": self.updated_at
        }

    def _get_balances(self):
        self.data = []
        if self.point_balance is not None and self.point_info:
            self.data.append(self._format_balance(self.point_balance, self.point_info, False))

        if self.value_balance is not None and self.value_info:
            self.data.append(self._format_balance(self.value_balance, self.value_info, True))


class MembershipCardSerializer(serializers.Serializer, MembershipTransactionsMixin):

    @staticmethod
    def _get_ubiquity_images(tier, images):
        # by using a dictionary duplicates are overwritten (if two hero are present only one will be returned)
        filtered_images = {
            image.image_type_code: image
            for image in images
            if image.image_type_code in [image.HERO, image.ICON] or (
                image.image_type_code == image.TIER and image.reward_tier == tier)
        }

        return UbiquityImageSerializer(list(filtered_images.values()), many=True).data

    def _get_transactions(self, instance):
        return self.get_transactions_data(
            self.context['request'].user.id, instance.id
        ) if self.context.get('request') and instance.scheme.has_transactions else []

    @staticmethod
    def get_translated_status(instance: 'SchemeAccount') -> dict:
        status = instance.status
        if status in instance.SYSTEM_ACTION_REQUIRED:
            status = instance.ACTIVE
            if not instance.balances:
                status = instance.PENDING

        return {
            'state': ubiquity_status_translation[status],
            'reason_codes': [
                reason_code_translation[status],
            ]
        }

    def to_representation(self, instance: 'SchemeAccount') -> dict:
        query = {
            'scheme_account': instance,
            'payment_card_account__is_deleted': False
        }
        payment_cards = PaymentCardSchemeEntry.objects.filter(**query).all()
        images = instance.scheme.images.all()
        exclude_balance_statuses = instance.EXCLUDE_BALANCE_STATUSES

        if instance.status not in exclude_balance_statuses:
            # instance.get_cached_balance()
            async_balance.delay(instance.id)

        try:
            reward_tier = instance.balances[0]['reward_tier']
        except (ValueError, KeyError):
            reward_tier = 0

        return {
            'id': instance.id,
            'membership_plan': instance.scheme.id,
            'payment_cards': PaymentCardLinksSerializer(payment_cards, many=True).data,
            'membership_transactions': self._get_transactions(instance),
            'status': self.get_translated_status(instance),
            'card': {
                'barcode': instance.barcode,
                'membership_id': instance.card_number,
                'barcode_type': instance.scheme.barcode_type,
                'colour': instance.scheme.colour
            },
            'images': self._get_ubiquity_images(reward_tier, images),
            'account': {
                'tier': reward_tier
            },
            'balances': UbiquityBalanceHandler(instance.balances, many=True).data if instance.balances else None
        }


# not used for now but will be needed
# class ListMembershipCardSerializer(MembershipCardSerializer):
#     @staticmethod
#     def _get_ubiquity_images(tier, images):
#         return [
#             image.id
#             for image in images
#             if image.image_type_code in [image.HERO, image.ICON] or (
#                     image.image_type_code == image.TIER and image.reward_tier == tier)
#         ]
#
#     def _get_transactions(self, instance):
#         return self.get_transactions_id(
#             self.context['request'].user.id, instance.id
#         ) if self.context.get('request') and instance.scheme.has_transactions else []


class LinkMembershipCardSerializer(CreateSchemeAccountSerializer):
    verify_account_exists = False


# todo adapt or remove
class JoinMembershipCardSerializer(JoinSerializer):
    pass


class PaymentCardReplaceSerializer(CreatePaymentCardAccountSerializer):
    token = serializers.CharField(max_length=255, write_only=True, source='psp_token')

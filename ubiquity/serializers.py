from decimal import Decimal
from decimal import ROUND_HALF_UP
import arrow
import jwt
import requests
from arrow.parser import ParserError
from django.conf import settings
from rest_framework import serializers

from payment_card.models import Issuer, PaymentCard
from payment_card.serializers import (PaymentCardAccountSerializer,
                                      get_images_for_payment_card_account)
from scheme.models import Scheme, SchemeBalanceDetails, SchemeCredentialQuestion, SchemeDetail
from scheme.serializers import CreateSchemeAccountSerializer
from ubiquity.models import PaymentCardSchemeEntry, ServiceConsent
from ubiquity.reason_codes import reason_code_translation, ubiquity_status_translation
from user.models import CustomUser


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
        return obj.payment_card_account.id

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
    first_six_digits = serializers.IntegerField(source='pan_start')
    last_four_digits = serializers.IntegerField(source='pan_end')
    year = serializers.IntegerField(source='expiry_year')
    month = serializers.IntegerField(source='expiry_month')
    token = None

    @staticmethod
    def get_membership_cards(obj):
        links = PaymentCardSchemeEntry.objects.filter(payment_card_account=obj).all()
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
    pan_start = serializers.IntegerField(source='first_six_digits')
    pan_end = serializers.IntegerField(source='last_four_digits')
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
        return Issuer.objects.get(name='Barclays').id

    @staticmethod
    def get_payment_card(_):
        return PaymentCard.objects.get(slug='launchpad-visa').id


class PaymentCardUpdateSerializer(serializers.Serializer):
    pan_start = serializers.IntegerField(source='first_six_digits', required=False)
    pan_end = serializers.IntegerField(source='last_four_digits', required=False)
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
        return obj.scheme_account.id

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


class MembershipPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scheme
        exclude = ('name',)

    @staticmethod
    def _get_ubiquity_images(instance):
        # by using a dictionary duplicates are overwritten (if two hero are present only one will be returned)
        filtered_images = {
            image.image_type_code: image
            for image in instance.images.all()
            if image.image_type_code in [image.HERO, image.ICON]
        }

        return UbiquityImageSerializer(list(filtered_images.values()), many=True).data

    def to_representation(self, instance):
        balances = instance.schemebalancedetails_set.all()
        tiers = instance.schemedetail_set.filter(type=0).all()
        add_fields = instance.questions.filter(field_type=0).all()
        authorise_fields = instance.questions.filter(field_type=1).all()
        enrol_fields = instance.questions.filter(field_type=2).all()
        status = 'active' if instance.is_active else 'suspended'
        if instance.tier == 2:
            card_type = 2
        elif instance.has_points or instance.has_transactions:
            card_type = 1
        else:
            card_type = 0

        return {
            'id': instance.id,
            'status': status,
            'feature_set': {
                'authorisation_required': instance.authorisation_required,
                'transactions_available': instance.has_transactions,
                'digital_only': instance.digital_only,
                'has_points': instance.has_points,
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
                ],
                'card_type': card_type
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
                'plan_name_card': instance.plan_name_card,
                'plan_url': instance.url,
                'plan_summary': instance.plan_summary,
                'plan_description': instance.plan_description,
                'company_name': instance.company,
                'company_url': instance.company_url,
                'enrol_incentive': instance.enrol_incentive,
                'category': instance.category.name,
                'forgotten_password_url': instance.forgotten_password_url,
                'tiers': SchemeDetailSerializer(tiers, many=True).data,
                'terms': instance.join_t_and_c,
                'terms_url': instance.join_url,
                'add_fields': SchemeQuestionSerializer(add_fields, many=True).data,
                'authorise_fields': SchemeQuestionSerializer(authorise_fields, many=True).data,
                'enrol_fields': SchemeQuestionSerializer(enrol_fields, many=True).data,
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

    def to_representation(self, instance):
        payment_cards = PaymentCardSchemeEntry.objects.filter(scheme_account=instance).all()
        images = instance.scheme.images.all()
        if instance.status != instance.FAILED_UPDATE:
            instance.get_cached_balance()

        try:
            reward_tier = instance.balances[0]['reward_tier']
        except (ValueError, KeyError):
            reward_tier = 0

        return {
            'id': instance.id,
            'membership_plan': instance.scheme.id,
            'payment_cards': PaymentCardLinksSerializer(payment_cards, many=True).data,
            'membership_transactions': self._get_transactions(instance),
            'status': {
                'state': ubiquity_status_translation[instance.status],
                'reason_codes': [
                    reason_code_translation[instance.status],
                ]
            },
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


class UbiquityCreateSchemeAccountSerializer(CreateSchemeAccountSerializer):
    verify_account_exists = False

import arrow
from arrow.parser import ParserError
from rest_framework import serializers

from payment_card.models import Issuer, PaymentCard
from payment_card.serializers import (PaymentCardAccountSerializer,
                                      get_images_for_payment_card_account)
from scheme.models import Scheme, SchemeBalanceDetails, SchemeCredentialQuestion, SchemeDetail
from scheme.serializers import (BalanceSerializer, GetSchemeAccountSerializer, ListSchemeAccountSerializer)
from ubiquity.models import PaymentCardSchemeEntry, ServiceConsent
from ubiquity.reason_codes import reason_code_translation
from user.models import CustomUser


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

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "membership_cards": self.get_membership_cards(instance),
            "status": instance.status,
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
            "images": get_images_for_payment_card_account(instance, serializer_class=UbiquityImageSerializer,
                                                          add_type=False),
            "account": {
                "consents": instance.consents
            }
        }


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

    @staticmethod
    def get_amounts(instance):
        scheme = Scheme.objects.get(schemeaccount__id=instance['scheme_account_id'])
        scheme_balances = scheme.schemebalancedetails_set.first()
        amounts = []

        if instance['value']:
            amounts.append(
                {
                    'currency': 'GBP',
                    'prefix': '£',
                    'suffix': None,
                    'value': instance['value']
                }
            )

        if instance['points']:
            amounts.append(
                {
                    'currency': scheme_balances.currency,
                    'prefix': scheme_balances.prefix,
                    'suffix': scheme_balances.suffix,
                    'value': instance['points']
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
    def _filter_images(instance):
        filtered_images = {
            image.image_type_code: image
            for image in instance.images.all()
            if image.image_type_code in [image.HERO, image.ICON]
        }

        return list(filtered_images.values())

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
                'has_balance': instance.has_points,
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
            'images': UbiquityImageSerializer(self._filter_images(instance), many=True).data,
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


class UbiquityBalanceSerializer(serializers.Serializer):
    scheme_balance = None
    value = serializers.CharField(required=False)
    currency = serializers.SerializerMethodField()
    prefix = serializers.SerializerMethodField()
    suffix = serializers.SerializerMethodField()
    updated_at = serializers.IntegerField(required=False)

    def get_currency(self, instance):
        if 'scheme_id' not in instance:
            return None
        scheme_balance = self.retrieve_scheme_balance_info(instance['scheme_id'])
        return scheme_balance.currency if scheme_balance else None

    def get_prefix(self, instance):
        if 'scheme_id' not in instance:
            return None
        scheme_balance = self.retrieve_scheme_balance_info(instance['scheme_id'])
        return scheme_balance.prefix if scheme_balance else None

    def get_suffix(self, instance):
        if 'scheme_id' not in instance:
            return None
        scheme_balance = self.retrieve_scheme_balance_info(instance['scheme_id'])
        return scheme_balance.suffix if scheme_balance else None

    def retrieve_scheme_balance_info(self, scheme_id):
        if self.scheme_balance:
            return self.scheme_balance

        scheme_balance = SchemeBalanceDetails.objects.filter(scheme_id=scheme_id).first()
        if scheme_balance:
            self.scheme_balance = scheme_balance
            return scheme_balance

        return None

    class Meta:
        exclude = ('scheme',)


class MembershipCardSerializer(serializers.Serializer):

    @staticmethod
    def _filter_images(tier, images):
        filtered_images = {
            image.image_type_code: image
            for image in images
            if image.image_type_code in [image.HERO, image.ICON] or (
                image.image_type_code == image.TIER and image.reward_tier == tier)
        }

        return list(filtered_images.values())

    def to_representation(self, instance):
        payment_cards = PaymentCardSchemeEntry.objects.filter(scheme_account=instance).all()
        images = instance.scheme.images.all()
        fields_type = {0: [], 1: [], 2: []}
        for answer in instance.schemeaccountcredentialanswer_set.all():
            if answer.question.field_type:
                fields_type[answer.question.field_type].append({
                    'column': answer.question.label,
                    'value': answer.clean_answer()
                })

        try:
            reward_tier = instance.balances[0]['reward_tier']
        except (ValueError, KeyError):
            reward_tier = 0

        return {
            'id': instance.id,
            'membership_plan': instance.scheme.id,
            'payment_cards': PaymentCardLinksSerializer(payment_cards, many=True).data,
            'membership_transactions': [],
            'status': {
                'state': instance.status,
                'reason_code': reason_code_translation[instance.status]
            },
            'card': {
                'barcode': instance.barcode,
                'membership_id': instance.card_number,
                'barcode_type': instance.scheme.barcode_type,
                'colour': instance.scheme.colour
            },
            'images': UbiquityImageSerializer(self._filter_images(reward_tier, images), many=True).data,
            'account': {
                'tier': reward_tier,
                'add_fields': fields_type[0],
                'authorise_fields': fields_type[1],
                'enrol_fields': fields_type[2]
            },
            'balances': UbiquityBalanceSerializer(instance.balances, many=True).data if instance.balances else None
        }


class CreateMembershipCardSerializer(ListSchemeAccountSerializer):
    scheme = serializers.PrimaryKeyRelatedField(source='scheme', read_only=True)

    @staticmethod
    def get_balances(obj):
        balances = obj.balances if obj.balances else None
        return BalanceSerializer(balances).data

    @staticmethod
    def get_payment_cards(obj):
        links = PaymentCardSchemeEntry.objects.filter(scheme_account=obj).all()
        return MembershipCardLinksSerializer(links, many=True).data

    class Meta(ListSchemeAccountSerializer.Meta):
        read_only_fields = GetSchemeAccountSerializer.Meta.read_only_fields + ('payment_cards', 'membership_plan')
        fields = ('id',
                  'status',
                  'order',
                  'created',
                  'action_status',
                  'status_name',
                  'barcode',
                  'card_label',
                  'images',
                  'balances',
                  'payment_cards',
                  'membership_plan')

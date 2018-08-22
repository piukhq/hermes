import arrow
from arrow.parser import ParserError
from rest_framework import serializers

from payment_card.serializers import PaymentCardAccountSerializer, PaymentCardAccountImageSerializer, \
    get_images_for_payment_card_account
from scheme.models import SchemeAccount
from scheme.serializers import (BalanceSerializer, GetSchemeAccountSerializer, ListSchemeAccountSerializer,
                                SchemeAccountImageSerializer)
from ubiquity.models import PaymentCardSchemeEntry, ServiceConsent
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

    def to_representation(self, instance):
        response = {'timestamp': int(instance.timestamp.timestamp())}
        if instance.latitude and instance.longitude:
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
    name = serializers.SerializerMethodField()

    @staticmethod
    def get_id(obj):
        return obj.scheme_account.id

    @staticmethod
    def get_name(obj):
        return str(obj.scheme_account)

    class Meta:
        model = PaymentCardSchemeEntrySerializer.Meta.model
        exclude = ('payment_card_account', 'scheme_account')


class UbiquityPaymentCardImageSerializer(PaymentCardAccountImageSerializer):
    type = serializers.IntegerField(source='image_type_code')
    url = serializers.ImageField(source='image')
    encoding = serializers.SerializerMethodField()

    class Meta(PaymentCardAccountImageSerializer.Meta):
        exclude = None
        fields = ('id', 'url', 'type', 'description', 'encoding')

    @staticmethod
    def get_encoding(obj):
        if obj.encoding:
            return obj.encoding

        try:
            return obj.image.name.split('.')[-1]
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
        return PaymentCardLinksSerializer(links, many=True).data

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
            "images": get_images_for_payment_card_account(instance, serializer_class=UbiquityPaymentCardImageSerializer,
                                                          add_type=False),
            "account": {
                "consents": instance.consents
            }
        }


class PaymentCardTranslationSerializer(serializers.Serializer):
    pan_start = serializers.IntegerField(source='first_six_digits')
    pan_end = serializers.IntegerField(source='last_four_digits')
    issuer = serializers.IntegerField()
    payment_card = serializers.IntegerField()
    name_on_card = serializers.CharField()
    token = serializers.CharField()
    fingerprint = serializers.CharField()
    expiry_year = serializers.IntegerField(source='year')
    expiry_month = serializers.IntegerField(source='month')
    country = serializers.CharField()
    order = serializers.IntegerField(required=False, default=0)
    currency_code = serializers.CharField(required=False, default='GBP')


class MembershipCardLinksSerializer(PaymentCardSchemeEntrySerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    @staticmethod
    def get_id(obj):
        return obj.payment_card_account.id

    @staticmethod
    def get_name(obj):
        return str(obj.payment_card_account)

    class Meta:
        model = PaymentCardSchemeEntrySerializer.Meta.model
        exclude = ('scheme_account', 'payment_card_account')


class UbiquityMembershipCardImageSerializer(SchemeAccountImageSerializer):
    type = serializers.IntegerField(source='image_type_code')
    url = serializers.ImageField(source='image')
    encoding = serializers.SerializerMethodField()

    class Meta(PaymentCardAccountImageSerializer.Meta):
        exclude = None
        fields = ('id', 'url', 'type', 'description', 'encoding')

    @staticmethod
    def get_encoding(obj):
        if obj.encoding:
            return obj.encoding

        try:
            return obj.image.name.split('.')[-1]
        except (IndexError, AttributeError):
            return None


class MembershipCardSerializer(GetSchemeAccountSerializer):
    balance = serializers.SerializerMethodField(read_only=True)
    payment_cards = serializers.SerializerMethodField()
    membership_plan = serializers.PrimaryKeyRelatedField(read_only=True, source='scheme')

    @staticmethod
    def get_balance(obj):
        balance = obj.balance if obj.balance else None
        return BalanceSerializer(balance).data

    @staticmethod
    def get_payment_cards(obj):
        links = PaymentCardSchemeEntry.objects.filter(scheme_account=obj).all()
        return MembershipCardLinksSerializer(links, many=True).data

    class Meta:
        model = SchemeAccount
        read_only_fields = ('status', 'payment_cards', 'membership_plan')
        fields = ('id',
                  'status',
                  'order',
                  'created',
                  'action_status',
                  'status_name',
                  'barcode',
                  'card_label',
                  'images',
                  'balance',
                  'payment_cards',
                  'membership_plan',
                  'link_date')


class ListMembershipCardSerializer(ListSchemeAccountSerializer):
    balance = serializers.SerializerMethodField(read_only=True)
    payment_cards = serializers.SerializerMethodField()
    membership_plan = serializers.PrimaryKeyRelatedField(source='scheme', read_only=True)

    @staticmethod
    def get_balance(obj):
        balance = obj.balance if obj.balance else None
        return BalanceSerializer(balance).data

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
                  'balance',
                  'payment_cards',
                  'membership_plan')


class TransactionsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    scheme_account_id = serializers.IntegerField()
    created = serializers.DateTimeField()
    date = serializers.DateField()
    description = serializers.CharField()
    location = serializers.CharField()
    points = serializers.IntegerField()
    value = serializers.CharField()
    hash = serializers.CharField()


class ActiveCardAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCardSchemeEntry
        fields = ()

import arrow
from arrow.parser import ParserError
from rest_framework import serializers

from payment_card.serializers import PaymentCardAccountSerializer
from scheme.serializers import GetSchemeAccountSerializer, ListSchemeAccountSerializer
from ubiquity.models import PaymentCardSchemeEntry, ServiceConsent
from user.models import CustomUser


class ServiceConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceConsent
        fields = '__all__'

    timestamp = serializers.IntegerField()

    @staticmethod
    def validate_user(user):
        try:
            user_obj = CustomUser.objects.get(pk=user)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User {} not found.".format(user))

        return user_obj

    @staticmethod
    def validate_timestamp(timestamp):
        try:
            datetime = arrow.get(timestamp).datetime
        except ParserError:
            raise serializers.ValidationError('timestamp field is not a timestamp.')

        return datetime


class PaymentCardConsentSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    timestamp = serializers.IntegerField()


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
        exclude = ('id', 'payment_card_account', 'scheme_account')


class PaymentCardSerializer(PaymentCardAccountSerializer):
    membership_cards = serializers.SerializerMethodField()

    @staticmethod
    def get_membership_cards(obj):
        links = PaymentCardSchemeEntry.objects.filter(payment_card_account=obj).all()
        return map(lambda link: PaymentCardLinksSerializer(link).data, links)

    class Meta(PaymentCardAccountSerializer.Meta):
        exclude = ('token', 'psp_token', 'user_set', 'scheme_account_set')
        read_only_fields = PaymentCardAccountSerializer.Meta.read_only_fields + ('membership_cards',)


class BalanceSerializer(serializers.Serializer):
    points = serializers.FloatField()
    value = serializers.FloatField()
    value_label = serializers.CharField()
    points_label = serializers.CharField()
    reward_tier = serializers.IntegerField()


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
        exclude = ('id', 'scheme_account', 'payment_card_account')


class MembershipCardSerializer(GetSchemeAccountSerializer):
    balance = BalanceSerializer(read_only=True)
    payment_cards = serializers.SerializerMethodField()

    @staticmethod
    def get_payment_cards(obj):
        links = PaymentCardSchemeEntry.objects.filter(scheme_account=obj).all()
        return map(lambda link: MembershipCardLinksSerializer(link).data, links)

    class Meta(GetSchemeAccountSerializer.Meta):
        exclude = ('updated', 'is_deleted', 'user_set')
        read_only_fields = GetSchemeAccountSerializer.Meta.read_only_fields + ('payment_cards',)


class ListMembershipCardSerializer(ListSchemeAccountSerializer):
    balance = BalanceSerializer(read_only=True)
    payment_cards = serializers.SerializerMethodField()

    @staticmethod
    def get_payment_cards(obj):
        links = PaymentCardSchemeEntry.objects.filter(scheme_account=obj).all()
        return map(lambda link: MembershipCardLinksSerializer(link).data, links)

    class Meta(ListSchemeAccountSerializer.Meta):
        fields = ListSchemeAccountSerializer.Meta.fields + ('balance', 'payment_cards')
        read_only_fields = GetSchemeAccountSerializer.Meta.read_only_fields + ('payment_cards',)

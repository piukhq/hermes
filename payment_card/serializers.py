from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from payment_card.models import PaymentCard, PaymentCardAccount


class PaymentCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCard


class PaymentCardAccountImageSerializer(serializers.Serializer):
    image_type_code = serializers.CharField()
    image_size_code = serializers.CharField()
    image = serializers.CharField()
    strap_line = serializers.CharField()
    image_description = serializers.CharField()
    url = serializers.URLField
    call_to_action = serializers.CharField()
    order = serializers.IntegerField()
    status = serializers.IntegerField()
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField()
    created = serializers.DateTimeField()


class PaymentCardAccountSerializer(serializers.ModelSerializer):
    status_name = serializers.ReadOnlyField()
    token = serializers.CharField(
        max_length=255,
        write_only=True,
        validators=[UniqueValidator(queryset=PaymentCardAccount.objects.filter(is_deleted=False))])
    images = PaymentCardAccountImageSerializer(many=True, read_only=True)

    class Meta:
        model = PaymentCardAccount
        extra_kwargs = {'token': {'write_only': True}}
        read_only_fields = ('status', )


class PaymentCardSchemeAccountSerializer(serializers.Serializer):
    scheme_id = serializers.ReadOnlyField()
    user_id = serializers.ReadOnlyField()
    scheme_account_id = serializers.ReadOnlyField()
    extra_kwargs = {'token': {'write_only': True}, 'user': {'required': False}}
    read_only_fields = ('status', 'order', )
    exclude = ('is_deleted', )


class UpdatePaymentCardAccountSerializer(PaymentCardAccountSerializer):

    def validate_payment_card(self, value):
        raise serializers.ValidationError("Cannot change payment card for payment card account.")

    class Meta(PaymentCardAccountSerializer.Meta):
        pass

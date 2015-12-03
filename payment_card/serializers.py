from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from payment_card.models import PaymentCard, PaymentCardAccount


class PaymentCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCard


class PaymentCardAccountSerializer(serializers.ModelSerializer):
    status_name = serializers.ReadOnlyField()
    token = serializers.CharField(
        max_length=255,
        write_only=True,
        validators=[UniqueValidator(queryset=PaymentCardAccount.objects.filter(is_deleted=False))])

    class Meta:
        model = PaymentCardAccount
        extra_kwargs = {'token': {'write_only': True}, 'user': {'required': False}}
        read_only_fields = ('status', 'order', )
        exclude = ('is_deleted', )


class UpdatePaymentCardAccountSerializer(PaymentCardAccountSerializer):

    def validate_payment_card(self, value):
        raise serializers.ValidationError("Cannot change payment card for payment card account.")

    class Meta(PaymentCardAccountSerializer.Meta):
        pass

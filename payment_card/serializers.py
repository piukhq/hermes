from copy import copy
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from payment_card.models import PaymentCard, PaymentCardAccount, PaymentCardImage, PaymentCardAccountImage


class PaymentCardImageSerializer(serializers.ModelSerializer):

    class Meta:
        model = PaymentCardImage


class PaymentCardSerializer(serializers.ModelSerializer):
    images = PaymentCardImageSerializer(many=True)

    class Meta:
        model = PaymentCard
        fields = ('id', 'images', 'input_label', 'is_active', 'name', 'scan_message', 'slug', 'system',
                  'type', 'url',)


class PaymentCardAccountImageSerializer(serializers.ModelSerializer):

    class Meta:
        model = PaymentCardAccountImage


class PaymentCardAccountSerializer(serializers.ModelSerializer):
    status_name = serializers.ReadOnlyField()
    psp_token = serializers.CharField(
        max_length=255,
        write_only=True,
        validators=[UniqueValidator(queryset=PaymentCardAccount.objects.filter(is_deleted=False))])
    images = serializers.SerializerMethodField()
    order = serializers.IntegerField()

    @staticmethod
    def get_images(payment_card_account):
        return get_images_for_payment_card_account(payment_card_account)

    class Meta:
        model = PaymentCardAccount
        extra_kwargs = {'psp_token': {'write_only': True}}
        read_only_fields = ('status', 'is_deleted')
        exclude = ('token',)


class PaymentCardAccountStatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = PaymentCardAccount
        fields = ('status',)


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


def add_object_type_to_image_response(data, type):
    new_data = copy(data)
    new_data['object_type'] = type
    return new_data


def get_images_for_payment_card_account(payment_card_account):
    account_images = PaymentCardAccountImage.objects.filter(payment_card_accounts__id=payment_card_account.id)
    payment_card_images = PaymentCardImage.objects.filter(payment_card=payment_card_account.payment_card)

    images = []

    for image in account_images:
        serializer = PaymentCardAccountImageSerializer(image)
        images.append(add_object_type_to_image_response(serializer.data, 'payment_card_account_image'))

    for image in payment_card_images:
        account_image = account_images.filter(image_type_code=image.image_type_code).first()
        if not account_image:
            # we have to turn the PaymentCardImage instance into a PaymentCardAccountImage
            account_image = PaymentCardAccountImage(
                id=image.id,
                image_type_code=image.image_type_code,
                size_code=image.size_code,
                image=image.image,
                strap_line=image.strap_line,
                description=image.description,
                url=image.url,
                call_to_action=image.call_to_action,
                order=image.order,
                created=image.created,
            )

            serializer = PaymentCardAccountImageSerializer(account_image)
            images.append(add_object_type_to_image_response(serializer.data, 'payment_card_image'))

    return images

from copy import copy

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from payment_card import models
from payment_card.models import PaymentCardAccount
from user.models import ClientApplication


class PaymentCardImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PaymentCardImage
        fields = '__all__'


class PaymentCardSerializer(serializers.ModelSerializer):
    images = PaymentCardImageSerializer(many=True)

    class Meta:
        model = models.PaymentCard
        fields = ('id', 'images', 'input_label', 'is_active', 'name', 'scan_message', 'slug', 'system',
                  'type', 'url',)


class PaymentCardAccountImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PaymentCardAccountImage
        exclude = ('payment_card_accounts', 'encoding')


class PaymentCardAccountSerializer(serializers.ModelSerializer):
    status_name = serializers.ReadOnlyField()
    # psp_token = serializers.CharField(
    #     max_length=255,
    #     write_only=True,
    #     validators=[UniqueValidator(queryset=PaymentCardAccount.objects.filter(is_deleted=False))])
    images = serializers.SerializerMethodField()
    order = serializers.IntegerField()
    pan_end = serializers.SerializerMethodField()

    # TODO(cl): this should be removed in favour of the commented-out block above.
    # we can't do this until the front-end is ready for an update.
    token = serializers.CharField(
        max_length=255,
        write_only=True,
        source='psp_token',
        validators=[UniqueValidator(queryset=models.PaymentCardAccount.objects.filter(is_deleted=False))])

    @staticmethod
    def get_images(payment_card_account):
        return get_images_for_payment_card_account(payment_card_account)

    # iOS bug fix: return five characters for the four digit pan_end.
    @staticmethod
    def get_pan_end(payment_card_account):
        return '•{}'.format(payment_card_account.pan_end)

    class Meta:
        model = models.PaymentCardAccount
        extra_kwargs = {'psp_token': {'write_only': True}}
        read_only_fields = ('status', 'is_deleted')
        # TODO(cl): when fixing the above TODO, remove psp_token from here.
        exclude = ('psp_token', 'consents', 'user_set', 'scheme_account_set')


class QueryPaymentCardAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PaymentCardAccount
        fields = '__all__'


class CreatePaymentCardAccountSerializer(serializers.ModelSerializer):
    # psp_token = serializers.CharField(
    #     max_length=255,
    #     write_only=True,
    #     validators=[UniqueValidator(queryset=PaymentCardAccount.objects.filter(is_deleted=False))])
    images = serializers.SerializerMethodField()
    order = serializers.IntegerField()

    # TODO(cl): this should be removed in favour of the commented-out block above.
    # we can't do this until the front-end is ready for an update.
    token = serializers.CharField(
        max_length=255,
        write_only=True,
        source='psp_token',
        validators=[UniqueValidator(queryset=models.PaymentCardAccount.objects.filter(is_deleted=False))])

    @staticmethod
    def get_images(payment_card_account):
        return get_images_for_payment_card_account(payment_card_account)

    class Meta:
        model = models.PaymentCardAccount
        extra_kwargs = {'psp_token': {'write_only': True}}
        read_only_fields = ('status', 'is_deleted')
        # TODO(cl): when fixing the above TODO, remove psp_token from here.
        exclude = ('psp_token', 'consents')


class PaymentCardAccountStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PaymentCardAccount
        fields = ('status',)


class PaymentCardSchemeAccountSerializer(serializers.Serializer):
    scheme_id = serializers.ReadOnlyField()
    user_id = serializers.ReadOnlyField()
    scheme_account_id = serializers.ReadOnlyField()
    extra_kwargs = {'token': {'write_only': True}, 'user': {'required': False}}
    read_only_fields = ('status', 'order',)
    exclude = ('is_deleted',)


class UpdatePaymentCardAccountSerializer(PaymentCardAccountSerializer):

    def validate_payment_card(self, value):
        raise serializers.ValidationError("Cannot change payment card for payment card account.")

    class Meta(PaymentCardAccountSerializer.Meta):
        pass


class ProviderStatusMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ProviderStatusMapping
        fields = ('provider_status_code', 'bink_status_code')


class PaymentCardField(serializers.RelatedField):
    def to_internal_value(self, data):
        return models.PaymentCardAccount.objects.get(token=data)

    def to_representation(self, value):
        return value.pk


class AuthTransactionSerializer(serializers.ModelSerializer):
    payment_card_token = PaymentCardField(source='payment_card_account',
                                          queryset=PaymentCardAccount.objects.all(), write_only=True)

    class Meta:
        model = models.AuthTransaction
        fields = ('time', 'amount', 'mid', 'third_party_id', 'auth_code', 'currency_code', 'payment_card_token')
        extra_kwargs = {
            'payment_card_account': {'write_only': True},
            'payment_card_token': {'write_only': True}
        }
        depth = 1


class PaymentCardClientSerializer(serializers.ModelSerializer):
    organisation = serializers.SlugRelatedField(read_only=True, slug_field='name')

    class Meta:
        model = ClientApplication
        fields = ('client_id', 'secret', 'organisation')


def add_object_type_to_image_response(data, type):
    new_data = copy(data)
    new_data['object_type'] = type
    return new_data


def get_images_for_payment_card_account(payment_card_account, serializer_class=PaymentCardAccountImageSerializer):
    account_images = models.PaymentCardAccountImage.objects.filter(payment_card_accounts__id=payment_card_account.id)
    payment_card_images = models.PaymentCardImage.objects.filter(payment_card=payment_card_account.payment_card)

    images = []

    for image in account_images:
        serializer = serializer_class(image)
        images.append(add_object_type_to_image_response(serializer.data, 'payment_card_account_image'))

    for image in payment_card_images:
        account_image = account_images.filter(image_type_code=image.image_type_code).first()
        if not account_image:
            # we have to turn the PaymentCardImage instance into a PaymentCardAccountImage
            account_image = models.PaymentCardAccountImage(
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
                encoding=image.encoding
            )

            serializer = serializer_class(account_image)
            images.append(add_object_type_to_image_response(serializer.data, 'payment_card_image'))

    return images

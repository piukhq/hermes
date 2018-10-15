from collections import OrderedDict

from django.contrib.auth.password_validation import validate_password as validate_pass
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.validators import UniqueValidator

from hermes.currencies import CURRENCIES
from scheme.models import SchemeAccount
from user.models import (ClientApplicationBundle, CustomUser, GENDERS, Setting, UserDetail, UserSetting,
                         valid_promo_code)


class ClientAppSerializerMixin(serializers.Serializer):
    """
    Mixin for the register and login serializer.
    Field values must match that of a known ClientApplication and one of its Bundles.
    """
    client_id = serializers.CharField()
    bundle_id = serializers.CharField()

    def validate(self, data):
        data = super().validate(data)
        client_id = data.get('client_id')
        bundle_id = data.get('bundle_id')
        self._check_client_app_bundle(client_id, bundle_id)
        return data

    def _check_client_app_bundle(self, client_id, bundle_id):
        if not ClientApplicationBundle.objects.filter(
                bundle_id=bundle_id,
                client_id=client_id).exists():
            raise serializers.ValidationError(
                'ClientApplicationBundle not found ({} for {})'.format(bundle_id, client_id))


class ApplicationKitSerializer(serializers.Serializer):
    client_id = serializers.CharField(write_only=True)
    kit_name = serializers.CharField(write_only=True)


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    api_key = serializers.CharField(read_only=True)
    uid = serializers.CharField(read_only=True)
    external_id = serializers.CharField(required=False, max_length=255)

    def create(self, validated_data):
        email = validated_data['email']
        password = validated_data['password']
        external_id = validated_data.get('external_id')
        client_id = validated_data.get('client_id')

        if client_id and external_id:
            user = CustomUser.objects.create_user(email, password, client_id=client_id, external_id=external_id)
        elif client_id:
            user = CustomUser.objects.create_user(email, password, client_id=client_id)
        else:
            user = CustomUser.objects.create_user(email, password)

        user.save()
        return user

    def validate_email(self, value):
        email = CustomUser.objects.normalize_email(value)
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("That user already exists")
        return email

    def validate_password(self, value):
        validate_pass(value)
        return value

    def to_representation(self, instance):
        ret = OrderedDict()
        ret['email'] = instance.email
        ret['api_key'] = instance.create_token()
        ret['uid'] = instance.uid
        return ret


class NewRegisterSerializer(ClientAppSerializerMixin, RegisterSerializer):

    def validate(self, data):
        data = super().validate(data)
        if CustomUser.objects.filter(client_id=data['client_id'], external_id=data['external_id']).exists():
            raise serializers.ValidationError("That user already exists")
        return data

    def validate_email(self, email):
        return email


class ApplyPromoCodeSerializer(serializers.Serializer):
    promo_code = serializers.CharField()

    def validate_promo_code(self, promo_code):
        if not valid_promo_code(promo_code):
            raise serializers.ValidationError('Invalid promo code: {}'.format(promo_code))
        return promo_code


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class NewLoginSerializer(ClientAppSerializerMixin, LoginSerializer):
    pass


class OrganisationTermsAndConditionsSerializer(serializers.Serializer):
    terms_and_conditions = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        validate_pass(value)
        return value

    def update(self, instance, validated_data):
        instance.set_password(validated_data['password'])
        instance.save()
        return instance


class TokenResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        validate_pass(value)
        return value

    def update(self, instance, validated_data):
        if instance.reset_token is None:
            raise ValueError
        else:
            instance.set_password(validated_data['password'])
            instance.reset_token = None
            instance.save()
            return instance


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDetail
        date_of_birth = serializers.DateField(required=False, allow_null=True)
        fields = ('first_name', 'last_name', 'date_of_birth', 'phone', 'address_line_1', 'address_line_2', 'city',
                  'region', 'postcode', 'country', 'notifications', 'pass_code', 'currency', 'gender')


class UserSerializer(serializers.ModelSerializer):
    def update(self, instance, validated_data):
        raise_errors_on_nested_writes('update', self, validated_data)
        user_detail_instance = UserDetail.objects.get(user=instance)
        email = validated_data.pop('email', None)
        if 'profile' in validated_data:
            if 'currency' in validated_data['profile']:
                currency_code = CURRENCIES.index(validated_data['profile']['currency'])
                validated_data['profile']['currency'] = currency_code
            user_detail_serializer = UserProfileSerializer(user_detail_instance,
                                                           data=validated_data['profile'],
                                                           partial=True)
            user_detail_serializer.is_valid(raise_exception=True)
            user_detail_serializer.save()

        if email:
            instance.email = email
            instance.save()
        return instance

    uid = serializers.CharField(read_only=True, required=False)
    email = serializers.EmailField(validators=[UniqueValidator(queryset=CustomUser.objects.all())], required=False)
    first_name = serializers.CharField(source='profile.first_name', required=False, allow_blank=True)
    last_name = serializers.CharField(source='profile.last_name', required=False, allow_blank=True)
    date_of_birth = serializers.DateField(source='profile.date_of_birth', required=False, allow_null=True)
    phone = serializers.CharField(source='profile.phone', required=False, allow_blank=True)
    address_line_1 = serializers.CharField(source='profile.address_line_1', required=False, allow_blank=True)
    address_line_2 = serializers.CharField(source='profile.address_line_2', required=False, allow_blank=True)
    gender = serializers.ChoiceField(source='profile.gender', required=False, allow_blank=True, choices=GENDERS)
    city = serializers.CharField(source='profile.city', required=False, allow_blank=True)
    region = serializers.CharField(source='profile.region', required=False, allow_blank=True)
    postcode = serializers.CharField(source='profile.postcode', required=False, allow_blank=True)
    country = serializers.CharField(source='profile.country', required=False, allow_blank=True)
    notifications = serializers.IntegerField(source='profile.notifications', required=False, allow_null=True)
    pass_code = serializers.CharField(source='profile.pass_code', required=False, allow_blank=True)
    referral_code = serializers.ReadOnlyField()

    class Meta:
        model = CustomUser
        fields = ('uid', 'email', 'first_name', 'last_name', 'date_of_birth', 'phone', 'address_line_1',
                  'address_line_2', 'city', 'region', 'postcode', 'country', 'notifications', 'pass_code', 'gender',
                  'referral_code')


class SchemeAccountsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        fields = ('scheme', 'pk')

    def to_representation(self, instance):
        ret = OrderedDict()
        ret['scheme_id'] = instance.scheme.pk
        ret['scheme_account_id'] = instance.pk
        return ret


class SchemeAccountSerializer(serializers.Serializer):
    scheme_slug = serializers.CharField(max_length=50)
    scheme_account_id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    status = serializers.IntegerField()
    status_name = serializers.CharField()
    action_status = serializers.CharField()
    credentials = serializers.CharField(max_length=300)


class FacebookRegisterSerializer(serializers.Serializer):
    user_id = serializers.CharField(max_length=600)
    access_token = serializers.CharField(max_length=120)


class TwitterRegisterSerializer(serializers.Serializer):
    access_token_secret = serializers.CharField(max_length=600)
    access_token = serializers.CharField(max_length=120)


class ResponseAuthSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=600)
    api_key = serializers.CharField()
    uid = serializers.CharField(read_only=True)


class ResetTokenSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    def update(self, instance, validated_data):
        instance.set_password(validated_data['password'])
        instance.save()
        return instance


class SettingSerializer(serializers.ModelSerializer):
    value_type = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()

    class Meta:
        model = Setting
        fields = ('slug', 'default_value', 'value_type', 'scheme', 'label', 'category')

    @staticmethod
    def get_value_type(setting):
        return setting.value_type_name

    @staticmethod
    def get_category(setting):
        return setting.category_name


class UserSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSetting
        fields = ('user', 'value')


class UpdateUserSettingSerializer(serializers.Serializer):
    slug1 = serializers.SlugField(required=True)
    slug2 = serializers.SlugField(required=False)
    slug3 = serializers.SlugField(required=False)

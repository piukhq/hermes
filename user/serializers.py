from collections import OrderedDict

from django.contrib.auth.password_validation import validate_password as validate_pass
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.validators import UniqueValidator

from hermes.currencies import CURRENCIES
from scheme.models import SchemeAccount
from user.models import (CustomUser, UserDetail, GENDERS, valid_promo_code, Setting, UserSetting,
                         ClientApplicationBundle)


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
    promo_code = serializers.CharField(required=False, allow_blank=True, write_only=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    api_key = serializers.CharField(read_only=True)

    def create(self, validated_data):
        email = validated_data['email']
        password = validated_data['password']
        promo_code = validated_data.get('promo_code')

        client_id = validated_data.get('client_id')
        if client_id:
            user = CustomUser.objects.create_user(email, password, promo_code, client_id=client_id)
        else:
            user = CustomUser.objects.create_user(email, password, promo_code)

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

    def validate_promo_code(self, value):
        if value and not valid_promo_code(value):
            raise serializers.ValidationError("Promo code is not valid")
        return value

    def to_representation(self, instance):
        ret = OrderedDict()
        ret['email'] = instance.email
        ret['api_key'] = instance.create_token()
        return ret


class NewRegisterSerializer(ClientAppSerializerMixin, RegisterSerializer):
    def validate(self, data):
        data = super().validate(data)
        email = CustomUser.objects.normalize_email(data['email'])
        if CustomUser.objects.filter(client_id=data['client_id'], email__iexact=email).exists():
            raise serializers.ValidationError("That user already exists")
        return data

    def validate_email(self, email):
        return email


class PromoCodeSerializer(serializers.Serializer):
    promo_code = serializers.CharField(write_only=True)
    valid = serializers.BooleanField(read_only=True)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class NewLoginSerializer(ClientAppSerializerMixin, LoginSerializer):
    pass


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
            user_detail_serializer.is_valid()
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


class FaceBookWebRegisterSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=600)
    clientId = serializers.CharField(max_length=120)
    redirectUri = serializers.CharField(max_length=120)


class FacebookRegisterSerializer(serializers.Serializer):
    user_id = serializers.CharField(max_length=600)
    access_token = serializers.CharField(max_length=120)
    promo_code = serializers.CharField(max_length=120, required=False, allow_blank=True)


class TwitterRegisterSerializer(serializers.Serializer):
    access_token_secret = serializers.CharField(max_length=600)
    access_token = serializers.CharField(max_length=120)
    promo_code = serializers.CharField(max_length=120, required=False, allow_blank=True)


class ResponseAuthSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=600)
    api_key = serializers.CharField()


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

from collections import OrderedDict
from mail_templated import send_mail
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.validators import UniqueValidator
from hermes.currencies import CURRENCIES
from hermes.settings import LETHE_URL, MEDIA_URL
from scheme.models import SchemeAccount
from user.models import CustomUser, UserDetail, GENDERS, valid_promo_code


class RegisterSerializer(serializers.Serializer):
    promo_code = serializers.CharField(required=False, allow_blank=True, write_only=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    api_key = serializers.CharField(read_only=True)

    def create(self, validated_data):
        email = validated_data['email']
        password = validated_data['password']
        promo_code = validated_data.get('promo_code')
        user = CustomUser.objects.create_user(email, password, promo_code)
        return user

    def validate_email(self, value):
        email = CustomUser.objects.normalize_email(value)
        if CustomUser.objects.filter(email=email).exists():
            raise serializers.ValidationError("That user already exists")
        return email

    def validate_promo_code(self, value):
        if value and not valid_promo_code(value):
            raise serializers.ValidationError("Promo code is not valid")
        return value

    def to_representation(self, instance):
        ret = OrderedDict()
        ret['email'] = instance.email
        ret['api_key'] = instance.create_token()
        return ret


class PromoCodeSerializer(serializers.Serializer):
    promo_code = serializers.CharField(write_only=True)
    valid = serializers.BooleanField(read_only=True)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def update(self, instance, validated_data):
        instance.set_password(validated_data['password'])
        instance.save()
        return instance


class TokenResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def update(self, instance, validated_data):
        instance.set_password(validated_data['password'])
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


class ForgottenPasswordSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=600)

    def update(self, validated_data, instance):
        validated_data.generate_reset_token()
        send_mail('email.tpl',
                  {'link': '{}/{}'.format(LETHE_URL, validated_data.reset_token.decode('UTF-8')),
                   'hermes_url': MEDIA_URL},
                  'emailservice@loyaltyangels.com',
                  [validated_data.email],
                  fail_silently=False)
        return validated_data


class ResetTokenSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    def update(self, instance, validated_data):
        instance.set_password(validated_data['password'])
        instance.save()
        return instance

from collections import OrderedDict
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.validators import UniqueValidator
from hermes.currencies import CURRENCIES
from scheme.models import SchemeAccount
from user.models import CustomUser, UserDetail


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(validators=[UniqueValidator(queryset=CustomUser.objects.all())])
    password = serializers.CharField()

    def create(self, validated_data):
        email = validated_data['email']
        password = validated_data['password']
        return CustomUser.objects.create_user(email, password)

    def to_representation(self, instance):
        ret = OrderedDict()
        ret['email'] = instance.email
        ret['uid'] = instance.uid
        return ret


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDetail
        date_of_birth = serializers.DateField(required=False, allow_null=True)
        fields = ('first_name', 'last_name', 'date_of_birth', 'phone', 'address_line_1', 'address_line_2', 'city',
                  'region', 'postcode', 'country', 'notifications', 'pass_code', 'currency')


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
    city = serializers.CharField(source='profile.city', required=False, allow_blank=True)
    region = serializers.CharField(source='profile.region', required=False, allow_blank=True)
    postcode = serializers.CharField(source='profile.postcode', required=False, allow_blank=True)
    country = serializers.CharField(source='profile.country', required=False, allow_blank=True)
    notifications = serializers.IntegerField(source='profile.notifications', required=False, allow_null=True)
    pass_code = serializers.CharField(source='profile.pass_code', required=False, allow_blank=True)
    currency = serializers.CharField(source='profile.currency', required=False, allow_blank=True)

    class Meta:
        model = CustomUser
        fields = ('uid', 'email', 'first_name', 'last_name', 'date_of_birth', 'phone', 'address_line_1',
                  'address_line_2', 'city', 'region', 'postcode', 'country', 'notifications', 'pass_code',
                  'currency')


class SchemeAccountsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        fields = ('scheme', 'pk')

    def to_representation(self, instance):
        ret = OrderedDict()
        ret['scheme_id'] = instance.scheme.pk
        ret['scheme_account_id'] = instance.pk
        return ret



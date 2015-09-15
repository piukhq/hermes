from collections import OrderedDict
from rest_framework import serializers
from user.models import CustomUser, UserDetail


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
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


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDetail
        fields = ('first_name', 'last_name', 'date_of_birth', 'phone', 'address_line_1', 'address_line_2', 'city',
                  'region', 'postcode', 'country', 'notifications', 'pass_code', 'currency')


class UserSerializer(serializers.ModelSerializer):
    def update(self, instance, validated_data):
        user_detail_instance = UserDetail.objects.get(user=instance)
        email = validated_data.pop('email', None)
        if email:
            instance.email = email
            instance.save()
        user_detail_serializer = UserProfileSerializer(user_detail_instance,
                                                       data=validated_data['profile'],
                                                       partial=True)
        user_detail_serializer.is_valid()
        user_detail_serializer.save()
        return instance


    uid = serializers.CharField(read_only=True, required=False)
    first_name = serializers.CharField(source='profile.first_name', required=False)
    last_name = serializers.CharField(source='profile.last_name', required=False)
    date_of_birth = serializers.CharField(source='profile.date_of_birth', required=False)
    phone = serializers.CharField(source='profile.phone', required=False)
    address_line_1 = serializers.CharField(source='profile.address_line_1', required=False)
    address_line_2 = serializers.CharField(source='profile.address_line_2', required=False)
    city = serializers.CharField(source='profile.city', required=False)
    region = serializers.CharField(source='profile.region', required=False)
    postcode = serializers.CharField(source='profile.postcode', required=False)
    country = serializers.CharField(source='profile.country', required=False)
    notifications = serializers.CharField(source='profile.notifications', required=False)
    pass_code = serializers.CharField(source='profile.pass_code', required=False)
    currency = serializers.CharField(source='profile.currency', required=False)

    class Meta:
        model = CustomUser
        fields = ('uid', 'email', 'first_name', 'last_name', 'date_of_birth', 'phone', 'address_line_1',
                  'address_line_2', 'city', 'region', 'postcode', 'country', 'notifications', 'pass_code',
                  'currency')


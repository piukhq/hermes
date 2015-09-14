from rest_framework import serializers
from user.models import CustomUser, UserDetail


class UserSerializer(serializers.ModelSerializer):
    def update(self, instance, validated_data):
        pass

    first_name = serializers.CharField(source='profile.first_name')
    last_name = serializers.CharField(source='profile.last_name')
    date_of_birth = serializers.CharField(source='profile.date_of_birth')
    phone = serializers.CharField(source='profile.phone')
    address_line_1 = serializers.CharField(source='profile.address_line_1')
    address_line_2 = serializers.CharField(source='profile.address_line_2')
    city = serializers.CharField(source='profile.city')
    region = serializers.CharField(source='profile.region')
    postcode = serializers.CharField(source='profile.postcode')
    country = serializers.CharField(source='profile.country')
    notifications = serializers.CharField(source='profile.notifications')
    pass_code = serializers.CharField(source='profile.pass_code')
    currency = serializers.CharField(source='profile.currency')

    class Meta:
        model = CustomUser
        fields = ('uid', 'email', 'first_name', 'last_name', 'date_of_birth', 'phone', 'address_line_1',
                  'address_line_2', 'city', 'region', 'postcode', 'country', 'notifications', 'pass_code',
                  'currency')


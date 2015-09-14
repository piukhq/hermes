from rest_framework import serializers
from user.models import CustomUser, UserDetail


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDetail


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(many=True)

    class Meta:
        model = CustomUser
        fields=('profile',)

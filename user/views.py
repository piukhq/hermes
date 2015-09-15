from django.shortcuts import render
from rest_framework.generics import RetrieveUpdateAPIView, get_object_or_404, CreateAPIView
from user.models import CustomUser
from user.serializers import UserSerializer, RegisterSerializer


class ForgottenPassword():
    pass


class Login():
    pass


# TODO: Could be merged with users
# Will require research, multiple serializers
# Password Handling
class Register(CreateAPIView):
    serializer_class = RegisterSerializer


class ResetPassword():
    pass


class Users(RetrieveUpdateAPIView):
    queryset = CustomUser.objects.all().select_related()
    serializer_class = UserSerializer
    lookup_field = 'uid'

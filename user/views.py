from django.shortcuts import render
from rest_framework.generics import RetrieveUpdateAPIView, get_object_or_404
from user.models import CustomUser
from user.serializers import UserSerializer


class Users(RetrieveUpdateAPIView):
    queryset = CustomUser.objects.all().select_related()
    serializer_class = UserSerializer
    lookup_field = 'uid'

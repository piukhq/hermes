import json
from django.contrib.auth import authenticate, login
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from rest_framework.generics import RetrieveUpdateAPIView, get_object_or_404, CreateAPIView, UpdateAPIView
from user.models import CustomUser
from user.serializers import UserSerializer, RegisterSerializer, LoginSerializer


class ForgottenPassword():
    pass


class Login(View):
    @method_decorator(csrf_exempt)
    def post(self, request):
        email = request.POST['email']
        password = request.POST['password']
        user = authenticate(email=email, password=password)
        if user is not None:
            if user.is_active:
                print('login sucess')
                login(request, user)
                return HttpResponse(json.dumps({'email': email, 'uid': user.uid}), content_type="application/json")
            else:
                # Return a 'disabled account' error message
                pass
        else:
            pass
            # Return an
        return HttpResponse('result')


# TODO: Could be merged with users
# Will require research, multiple serializers
# Password Handling
class Register(CreateAPIView):
    serializer_class = RegisterSerializer


class ResetPassword(UpdateAPIView):
    pass


class Users(RetrieveUpdateAPIView):
    queryset = CustomUser.objects.all().select_related()
    serializer_class = UserSerializer
    lookup_field = 'uid'

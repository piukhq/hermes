import json
from django.contrib.auth import authenticate, login
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.generics import RetrieveUpdateAPIView, CreateAPIView, UpdateAPIView, ListAPIView, GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from scheme.models import SchemeAccount
from user.authenticators import UIDAuthentication
from user.models import CustomUser
from user.serializers import UserSerializer, RegisterSerializer, SchemeAccountsSerializer, LoginSerializer



class ForgottenPassword():
    pass


class Login(GenericAPIView):
    serializer_class = LoginSerializer

    def post(self, request):
        email = request.data['email']
        password = request.data['password']
        user = authenticate(email=email, password=password)

        if not user:
            return Response({"error": 'Login credentials incorrect.'}, status=403)
        if not user.is_active:
            return Response({"error": "The account associated with this email address is suspended."}, status=403)

        login(request, user)
        return Response({'email': email, 'api_key': user.uid})


# TODO: Could be merged with users
# Will require research, multiple serializers
# Password Handling
class Register(CreateAPIView):
    serializer_class = RegisterSerializer


class ResetPassword(UpdateAPIView):
    pass


class Users(RetrieveUpdateAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    queryset = CustomUser.objects.all().select_related()
    serializer_class = UserSerializer
    lookup_field = 'uid'


class Authenticate(APIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    @method_decorator(csrf_exempt)
    def get(self, request):
        return HttpResponse(json.dumps({
            'uid': str(request.user.uid),
            'id': str(request.user.id)
        }))


class SchemeAccounts(ListAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = SchemeAccountsSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(SchemeAccount.objects.filter(user=request.user))

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

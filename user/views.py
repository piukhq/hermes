import json
from types import SimpleNamespace
from urllib.parse import parse_qsl
from django.contrib.auth import authenticate, login
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import requests
from rest_framework.generics import RetrieveUpdateAPIView, CreateAPIView, UpdateAPIView, GenericAPIView,\
    RetrieveAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from hermes import settings
from scheme.encyption import AESCipher
from scheme.models import SchemeAccount, Scheme, SchemeCredentialQuestion, SchemeAccountCredentialAnswer
from user.authenticators import UIDAuthentication
from rest_framework.authentication import SessionAuthentication
from user.models import CustomUser
from user.serializers import UserSerializer, RegisterSerializer, SchemeAccountSerializer, LoginSerializer

class ForgottenPassword():
    pass


# TODO: don't override this and support csrf
class CustomSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


class Login(GenericAPIView):
    authentication_classes = (CustomSessionAuthentication,)
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
    authentication_classes = (CustomSessionAuthentication,)
    serializer_class = RegisterSerializer


class ResetPassword(UpdateAPIView):
    pass


class Users(RetrieveUpdateAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    queryset = CustomUser.objects.all().select_related()
    serializer_class = UserSerializer
    lookup_field = 'uid'

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


class Authenticate(APIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    @method_decorator(csrf_exempt)
    def get(self, request):
        return HttpResponse(json.dumps({
            'uid': str(request.user.uid),
            'id': str(request.user.id)
        }))


class RetrieveSchemeAccount(RetrieveAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = SchemeAccountSerializer

    def get(self, request, *args, **kwargs):
        scheme_account = get_object_or_404(SchemeAccount, user=request.user, pk=kwargs['scheme_account_id'])
        scheme = scheme_account.scheme
        credentials = {}
        security_questions = SchemeCredentialQuestion.objects.filter(scheme=scheme)
        if security_questions:
            for security_question in security_questions:
                answer = SchemeAccountCredentialAnswer.objects.get(scheme_account=scheme_account,
                                                                   type=security_question.type)
                credentials[security_question.type] = answer.answer

        serialized_credentials = json.dumps(credentials)
        encrypted_credentials = AESCipher(settings.AES_KEY.encode()).encrypt(serialized_credentials).decode('utf-8')

        instance = SimpleNamespace(scheme_slug=scheme.slug,
                                   user_id=request.user.id,
                                   scheme_account_id=scheme_account.id,
                                   credentials=encrypted_credentials)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class SocialLogin(APIView):
    def post(self, request):
        access_token_url = 'https://graph.facebook.com/v2.3/oauth/access_token'
        graph_api_url = 'https://graph.facebook.com/v2.3/me?fields=email,name,id'

        params = {
            'client_id': request.json['clientId'],
            'redirect_uri': request.json['redirectUri'],
            'client_secret': 'bb1adac0eba3747f8846cf72d49f0574',
            'code': request.json['code']
        }

        # Step 1. Exchange authorization code for access token.
        r = requests.get(access_token_url, params=params)

        # Step 2. Retrieve information about the current user.
        r = requests.get(graph_api_url, params=r.json())
        profile = json.loads(r.text)

        # Step 4. Create a new account or return an existing one.
        from django.utils.crypto import get_random_string
        password = get_random_string(length=32)
        user = CustomUser.objects.get(facebook=profile['id'])
        if not user:
            user = CustomUser(email=profile['email'], password=password, facebook=profile['id'])

        return Response({'email': user.email, 'api_key': user.uid})

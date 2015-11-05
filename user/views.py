import json
from types import SimpleNamespace
from django.contrib.auth import authenticate, login
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import requests
from requests_oauthlib import OAuth1Session
from rest_framework.generics import RetrieveUpdateAPIView, CreateAPIView, UpdateAPIView, GenericAPIView,\
    RetrieveAPIView, get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from scheme.models import SchemeAccount
from rest_framework.authentication import SessionAuthentication
from user.models import CustomUser
from user.serializers import UserSerializer, RegisterSerializer, SchemeAccountSerializer, LoginSerializer, \
    FaceBookWebRegisterSerializer, SocialRegisterSerializer
from django.conf import settings


class ForgottenPassword:
    pass


class OpenAuthentication(SessionAuthentication):
    """
    We need to disable csrf as we are running hermes on production through a proxy.
    Also we don't need csrf as we are using jwt tokens.
    """
    def enforce_csrf(self, request):
        return


# TODO: Could be merged with users
# Will require research, multiple serializers
# Password Handling
class Register(CreateAPIView):
    """
    Register a new user in the Loyalty Angels App.
    """
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer


class ResetPassword(UpdateAPIView):
    pass


class Users(RetrieveUpdateAPIView):
    """
    Get and update users account information.
    """
    queryset = CustomUser.objects
    serializer_class = UserSerializer

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, id=self.request.user.id)

        self.check_object_permissions(self.request, obj)
        return obj


class Authenticate(APIView):
    @method_decorator(csrf_exempt)
    def get(self, request):
        """
        Authenticate the user based on the Authorization header parameter.
        ---
        type:
          uid:
            required: true
            type: json
          id:
            required: true
            type: json

        """
        return Response({
            'uid': str(request.user.uid),
            'id': str(request.user.id)
        })


class RetrieveSchemeAccount(RetrieveAPIView):
    serializer_class = SchemeAccountSerializer

    def get(self, request, *args, **kwargs):
        """
        Retrieve a users scheme accounts.
        ---
        responseMessages:
            - code: 404
              message: Error retrieving scheme accounts for this user.
        """
        scheme_account = get_object_or_404(SchemeAccount, user=request.user, pk=kwargs['scheme_account_id'])
        scheme = scheme_account.scheme

        instance = SimpleNamespace(scheme_slug=scheme.slug,
                                   user_id=request.user.id,
                                   scheme_account_id=scheme_account.id,
                                   status=scheme_account.status,
                                   status_name=scheme_account.status_name,
                                   credentials=scheme_account.credentials())
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class Login(GenericAPIView):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request):
        """
        User login for the Loyalty Angels App
        ---
        type:
          api_key:
            required: true
            type: json
          email:
            required: true
            type: json
        responseMessages:
            - code: 403
              message: Login credentials incorrect.
            - code: 403
              message: The account associated with this email address is suspended.

        """
        email = request.data['email']
        password = request.data['password']
        user = authenticate(username=email, password=password)

        if not user:
            return Response({"message": 'Login credentials incorrect.'}, status=403)
        if not user.is_active:
            return Response({"message": "The account associated with this email address is suspended."}, status=403)

        login(request, user)
        return Response({'email': email, 'api_key': user.create_token()})


class FaceBookLoginWeb(CreateAPIView):
    """
    This is only used by ching web
    """
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = FaceBookWebRegisterSerializer

    def post(self, request, *args, **kwargs):
        access_token_url = 'https://graph.facebook.com/v2.3/oauth/access_token'
        params = {
            'client_id': request.data['clientId'],
            'redirect_uri': request.data['redirectUri'],
            'client_secret': settings.FACEBOOK_CLIENT_SECRET,
            'code': request.data['code']
        }
        # Exchange authorization code for access token.
        r = requests.get(access_token_url, params=params)
        if not r.ok:
            return Response({"error": 'Cannot get facebook user token.'}, status=403)

        return facebook_graph(r.json()['access_token'])


class FaceBookLogin(CreateAPIView):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)

    serializer_class = SocialRegisterSerializer

    def post(self, request, *args, **kwargs):
        """
        Login using a Facebook account.
        ---
        type:
          api_key:
            required: true
            type: json
          email:
            required: true
            type: json
        responseMessages:
            - code: 403
              message: Cannot validate user_id & access_token.
            - code: 403
              message: user_id is invalid for given access token.
            - code: 403
              message: Can not access facebook social graph.

        """
        access_token = request.data['access_token']
        user_id = request.data['user_id']
        r = requests.get("https://graph.facebook.com/me?access_token={0}".format(access_token))
        if not r.ok:
            return Response({"error": "Cannot validate user_id & access_token."}, status=403)
        if r.json()['id'] != user_id.strip():
            return Response({"error": "user_id is invalid for given access token"}, status=403)
        return facebook_graph(access_token)


def facebook_graph(access_token):
    params = {"access_token": access_token,
              "fields": "email,name,id"}
    # Retrieve information about the current user.
    r = requests.get('https://graph.facebook.com/v2.3/me', params=params)
    if not r.ok:
        return Response({"message": 'Can not access facebook social graph.'}, status=403)
    profile = r.json()
    # Create a new account or return an existing one.
    try:
        user = CustomUser.objects.get(facebook=profile['id'])
    except CustomUser.DoesNotExist:
        password = get_random_string(length=32)
        try:
            # See if they have an email in our system
            user = CustomUser.objects.get(email=profile['email'])
            user.facebook = profile['id']
            user.save()
        except CustomUser.DoesNotExist:
            user = CustomUser.objects.create(email=profile['email'], password=password, user=profile['id'])
        except KeyError:
            user = CustomUser.objects.create(password=password, user=profile['id'])

    return Response({'email': user.email, 'api_key': user.create_token()})


class TwitterLogin(APIView):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = SocialRegisterSerializer

    def post(self, request, *args, **kwargs):
        """
        Login using a Twitter account.

        """
        request_token_url = 'https://api.twitter.com/oauth/request_token'
        access_token_url = 'https://api.twitter.com/oauth/access_token'

        if request.data.get('oauth_token') and request.data.get('oauth_verifier'):
            oauth_session = OAuth1Session(settings.TWITTER_CONSUMER_KEY,
                                          client_secret=settings.TWITTER_CONSUMER_SECRET,
                                          resource_owner_key=request.data['oauth_token'],
                                          verifier=request.data['oauth_verifier'])
            access_token = oauth_session.fetch_access_token(access_token_url)

            try:
                user = CustomUser.objects.get(twitter=access_token['user_id'])
            except CustomUser.DoesNotExist:
                password = get_random_string(length=32)
                user = CustomUser.objects.create(password=password, twitter=access_token['user_id'])

            return Response({'email': user.email, 'api_key': user.create_token()})

        oauth_session = OAuth1Session(settings.TWITTER_CONSUMER_KEY,
                                      client_secret=settings.TWITTER_CONSUMER_SECRET,
                                      callback_uri=settings.TWITTER_CALLBACK_URL)
        request_token = oauth_session.fetch_request_token(request_token_url)
        return Response(request_token)

import requests
from django.contrib.auth import authenticate, login
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from requests_oauthlib import OAuth1Session
from rest_framework.generics import (RetrieveUpdateAPIView, CreateAPIView, UpdateAPIView, GenericAPIView,
                                     get_object_or_404)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication
from user.models import CustomUser
from django.conf import settings
from user.serializers import (UserSerializer, RegisterSerializer, LoginSerializer, FaceBookWebRegisterSerializer,
                              SocialRegisterSerializer, ResponseAuthSerializer, ResetPasswordSerializer)


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
    serializer_class = ResetPasswordSerializer

    def get_object(self):
        obj = get_object_or_404(CustomUser, id=self.request.user.id)
        self.check_object_permissions(self.request, obj)
        return obj


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
        response_serializer: ResponseAuthSerializer
        """
        email = self.lower_email_domain(request.data['email'])
        password = request.data['password']
        user = authenticate(username=email, password=password)

        if not user:
            return Response({"message": 'Login credentials incorrect.'}, status=403)
        if not user.is_active:
            return Response({"message": "The account associated with this email address is suspended."}, status=403)

        login(request, user)
        out_serializer = ResponseAuthSerializer({'email': user.email, 'api_key': user.create_token()})
        return Response(out_serializer.data)

    @staticmethod
    def lower_email_domain(email):
        parts = email.rsplit("@")
        return "@".join(parts[:-1] + [parts[-1].lower()])


class FaceBookLoginWeb(CreateAPIView):
    """
    This is only used by ching web
    """
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = FaceBookWebRegisterSerializer

    def post(self, request, *args, **kwargs):
        """
        ---
        response_serializer: ResponseAuthSerializer
        """
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

        return facebook_login(r.json()['access_token'])


class FaceBookLogin(CreateAPIView):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)

    serializer_class = SocialRegisterSerializer

    def post(self, request, *args, **kwargs):
        """
        Login using a Facebook account.
        ---
        type:
          access_token:
            required: true
            type: json
          user_id:
            required: true
            type: json
        responseMessages:
            - code: 403
              message: Cannot validate user_id & access_token.
            - code: 403
              message: user_id is invalid for given access token.
            - code: 403
              message: Can not access facebook social graph.
        response_serializer: ResponseAuthSerializer
        """
        access_token = request.data['access_token']
        user_id = request.data['user_id']
        r = requests.get("https://graph.facebook.com/me?access_token={0}".format(access_token))
        if not r.ok:
            return Response({"error": "Cannot validate user_id & access_token."}, status=403)
        if r.json()['id'] != user_id.strip():
            return Response({"error": "user_id is invalid for given access token"}, status=403)
        return facebook_login(access_token)


def facebook_login(access_token):
    params = {"access_token": access_token, "fields": "email,name,id"}
    # Retrieve information about the current user.
    r = requests.get('https://graph.facebook.com/v2.3/me', params=params)
    if not r.ok:
        return Response({"message": 'Can not access facebook social graph.'}, status=403)
    profile = r.json()
    status, user = social_login(profile['id'], profile.get('email'), 'facebook')

    out_serializer = ResponseAuthSerializer({'email': user.email, 'api_key': user.create_token()})
    return Response(out_serializer.data, status)


class TwitterLoginWeb(APIView):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        """
        Login using a Twitter account from web app.
        ---
        response_serializer: ResponseAuthSerializer
        """
        request_token_url = 'https://api.twitter.com/oauth/request_token'
        access_token_url = 'https://api.twitter.com/oauth/access_token'

        if request.data.get('oauth_token') and request.data.get('oauth_verifier'):
            oauth_session = OAuth1Session(settings.TWITTER_CONSUMER_KEY,
                                          client_secret=settings.TWITTER_CONSUMER_SECRET,
                                          resource_owner_key=request.data['oauth_token'],
                                          verifier=request.data['oauth_verifier'])
            access_token = oauth_session.fetch_access_token(access_token_url)
            return twitter_login(access_token['oauth_token'], access_token['oauth_token_secret'])

        oauth_session = OAuth1Session(settings.TWITTER_CONSUMER_KEY,
                                      client_secret=settings.TWITTER_CONSUMER_SECRET,
                                      callback_uri=settings.TWITTER_CALLBACK_URL)
        request_token = oauth_session.fetch_request_token(request_token_url)
        return Response(request_token)


class TwitterLogin(APIView):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        """
        Login using a Twitter account.
        ---
        response_serializer: ResponseAuthSerializer
        """
        return twitter_login(request.data['access_token'], request.data['access_token_secret'])


def twitter_login(access_token, access_token_secret):
    """
    https://dev.twitter.com/web/sign-in/implementing
    https://dev.twitter.com/rest/reference/get/account/verify_credentials
    """
    oauth_session = OAuth1Session(settings.TWITTER_CONSUMER_KEY,
                                  client_secret=settings.TWITTER_CONSUMER_SECRET,
                                  resource_owner_key=access_token,
                                  resource_owner_secret=access_token_secret)

    params = {'skip_status': 'true', 'include_entities': 'false', 'include_email': 'true'}
    request = oauth_session.get("https://api.twitter.com/1.1/account/verify_credentials.json", params=params)

    if not request.ok:
        # TODO: add logging
        return Response(request.json()['errors'], status=request.status_code)

    profile = request.json()
    status, user = social_login(profile['id_str'], profile.get('email'), 'twitter')
    out_serializer = ResponseAuthSerializer({'email': user.email, 'api_key': user.create_token()})
    return Response(out_serializer.data, status=status)


def social_login(social_id, email, service):
    status = 200
    try:
        user = CustomUser.objects.get(**{service: social_id})
        if not user.email and email:
            user.email = email
            user.save()
    except CustomUser.DoesNotExist:
        try:
            if not email:
                raise CustomUser.DoesNotExist
            # User exists in our system but hasn't been linked
            user = CustomUser.objects.get(email=email)
            setattr(user, service, social_id)
            user.save()
        except CustomUser.DoesNotExist:
            password = get_random_string(length=32)
            user = CustomUser.objects.create(**{'email': email, 'password': password, service: social_id})
            status = 201
    return status, user

import requests
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from errors import (FACEBOOK_BAD_TOKEN, FACEBOOK_CANT_VALIDATE, FACEBOOK_GRAPH_ACCESS, FACEBOOK_INVALID_USER,
                    INCORRECT_CREDENTIALS, REGISTRATION_FAILED, SUSPENDED_ACCOUNT, error_response)
from mail_templated import send_mail
from requests_oauthlib import OAuth1Session
from rest_framework import mixins
from rest_framework.generics import (CreateAPIView, GenericAPIView, ListAPIView,
                                     RetrieveUpdateAPIView, get_object_or_404)
from rest_framework.authentication import SessionAuthentication
from rest_framework.mixins import UpdateModelMixin
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import (HTTP_200_OK, HTTP_204_NO_CONTENT,
                                   HTTP_400_BAD_REQUEST)
from rest_framework.views import APIView
from hermes.settings import LETHE_URL, MEDIA_URL
from intercom import intercom_api
from user.authentication import JwtAuthentication
from user.models import (ClientApplication, ClientApplicationKit, CustomUser, Setting, UserSetting, valid_reset_code)
from user.serializers import (ApplicationKitSerializer,
                              FaceBookWebRegisterSerializer, FacebookRegisterSerializer, LoginSerializer,
                              NewLoginSerializer, NewRegisterSerializer, ApplyPromoCodeSerializer,
                              RegisterSerializer, ResetPasswordSerializer, ResetTokenSerializer,
                              ResponseAuthSerializer, SettingSerializer, TokenResetPasswordSerializer,
                              TwitterRegisterSerializer, UserSerializer, UserSettingSerializer)


class OpenAuthentication(SessionAuthentication):
    """
    We need to disable csrf as we are running hermes on production through a proxy.
    Also we don't need csrf as we are using jwt tokens.
    """

    def enforce_csrf(self, request):
        return


class CustomRegisterMixin(object):
    def register_user(self, request, serializer_class):
        serializer = serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()

            user = CustomUser.objects.filter(email__iexact=request.data['email']).first()
            if user:
                send_mail('register_email.tpl',
                          {'user': user},
                          'Bink HQ <noreply@bink.com>',
                          [user.email],
                          fail_silently=False)
            return Response(serializer.data, 201)
        else:
            return error_response(REGISTRATION_FAILED)


# TODO: Could be merged with users
# Will require research, multiple serializers
# Password Handling
class Register(CustomRegisterMixin, APIView):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def post(self, request):
        """
        Register a new user in the Loyalty Angels App.
        ---
        request_serializer: RegisterSerializer
        response_serializer: RegisterSerializer
        parameters:
            - name: password
              description: >
                password must be at least 8 characters long and contain at least one lower case character, one upper
                case character, and one number.
        """
        return self.register_user(request, self.serializer_class)


class NewRegister(Register):
    """New Register for authorised app users.
    """
    serializer_class = NewRegisterSerializer


class ApplyPromoCode(CreateAPIView):
    """
    Apply a promo code to a user.
    """
    authentication_classes = (JwtAuthentication,)
    serializer_class = ApplyPromoCodeSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({'valid': False}, status=HTTP_200_OK)
        data = serializer.validated_data
        request.user.apply_promo_code(data['promo_code'])
        return Response({'valid': True}, status=HTTP_200_OK)


class ValidateResetToken(CreateAPIView):
    """
    DO NOT USE - NOT FOR APP ACCESS
    Validate a password reset token. Used internally by the password reset/password change functionality.
    """
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = ResetTokenSerializer

    def post(self, request, *args, **kwargs):
        reset_token = request.data['token']
        if not valid_reset_code(reset_token):
            return Response(status=404)
        out_serializer = ResetTokenSerializer({'valid': True})
        return Response(out_serializer.data)


class ResetPassword(mixins.UpdateModelMixin, GenericAPIView):
    """
    Reset a user's password
    """
    serializer_class = ResetPasswordSerializer

    def get_object(self):
        obj = get_object_or_404(CustomUser, id=self.request.user.id)
        self.check_object_permissions(self.request, obj)
        return obj

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


class ForgotPassword(APIView):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)

    def post(self, request):
        """
        Sends email with reset token to user.
        Responds: 'An email has been sent with details of how to reset your password.'
        """
        # TODO: Remove default Bink client_id when migrating to SDK app versions only (deprecation path).
        client_id = request.data.get('client_id', ClientApplication.get_bink_app().client_id)
        user = CustomUser.objects.filter(client_id=client_id, email__iexact=request.data['email']).first()
        if user:
            user.generate_reset_token()
            send_mail('email.tpl',
                      {'link': '{}/{}'.format(LETHE_URL, user.reset_token.decode('UTF-8')),
                       'hermes_url': MEDIA_URL},
                      'noreply@bink.com',
                      [user.email],
                      fail_silently=False)

        return Response('An email has been sent with details of how to reset your password.', 200)


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


class VerifyToken(APIView):
    """
    Basic view to check that a token is valid.
    Can be used by external services which don't know the secret.
    """

    def get(self, request):
        return Response()


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
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return error_response(INCORRECT_CREDENTIALS)

        credentials = self.get_credentials(serializer.data)
        user = authenticate(**credentials)

        if not user:
            return error_response(INCORRECT_CREDENTIALS)
        if not user.is_active:
            return error_response(SUSPENDED_ACCOUNT)

        login(request, user)
        out_serializer = ResponseAuthSerializer({'email': user.email, 'api_key': user.create_token()})
        return Response(out_serializer.data)

    @classmethod
    def get_credentials(cls, data):
        credentials = {
            'username': CustomUser.objects.normalize_email(data['email']),
            'password': data['password'],
        }
        return credentials


class NewLogin(Login):
    """New login view for users of an authorised app.
    """
    serializer_class = NewLoginSerializer

    @classmethod
    def get_credentials(cls, data):
        client_key = 'client_id'
        credentials = super().get_credentials(data)
        credentials.update({
            client_key: data[client_key],
        })
        return credentials


class FaceBookLoginWeb(CreateAPIView):
    """
    This is only used by web app
    """
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = FaceBookWebRegisterSerializer

    def post(self, request, *args, **kwargs):
        """
        Login using a Facebook account from web app
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
            return error_response(FACEBOOK_BAD_TOKEN)

        return facebook_login(r.json()['access_token'])


class FaceBookLogin(CreateAPIView):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)

    serializer_class = FacebookRegisterSerializer

    def post(self, request, *args, **kwargs):
        """
        Login using a Facebook account.
        ---
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
            return error_response(FACEBOOK_CANT_VALIDATE)
        if r.json()['id'] != user_id.strip():
            return error_response(FACEBOOK_INVALID_USER)
        return facebook_login(access_token)


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


class TwitterLogin(CreateAPIView):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)

    serializer_class = TwitterRegisterSerializer

    def post(self, request, *args, **kwargs):
        """
        Login using a Twitter account.
        ---
        response_serializer: ResponseAuthSerializer
        """
        return twitter_login(request.data['access_token'], request.data['access_token_secret'])


class ResetPasswordFromToken(CreateAPIView, UpdateModelMixin):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = TokenResetPasswordSerializer

    def post(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS.\n
        Reset a user's password using a reset token obtained via password reset email. Returns empty object.
        ---
        parameters:
            - name: token
              description: password reset token
        """
        return self.update(request, *args, **kwargs)

    def get_object(self):
        reset_token = self.request.data['token']
        obj = get_object_or_404(CustomUser, reset_token=reset_token)
        if not valid_reset_code(reset_token):
            raise Http404

        return obj


def facebook_login(access_token):
    params = {"access_token": access_token, "fields": "email,name,id"}
    # Retrieve information about the current user.
    r = requests.get('https://graph.facebook.com/v2.3/me', params=params)
    if not r.ok:
        return error_response(FACEBOOK_GRAPH_ACCESS)
    profile = r.json()
    return social_response(profile['id'], profile.get('email'), 'facebook')


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

    # twitter can send back an empty string, and we need a None
    email = profile.get('email')
    if not email:
        email = None
    return social_response(profile['id_str'], email, 'twitter')


def social_response(social_id, email, service):
    status, user = social_login(social_id, email, service)

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
            user = CustomUser.objects.get(email__iexact=email)
            setattr(user, service, social_id)
            user.save()
        except CustomUser.DoesNotExist:
            # We are creating a new user
            password = get_random_string(length=32)
            user = CustomUser.objects.create_user(**{'email': email, 'password': password, service: social_id})
            status = 201
    return status, user


class Settings(ListAPIView):
    """
    View the default app settings.
    """
    queryset = Setting.objects.all()
    serializer_class = SettingSerializer
    authentication_classes = (JwtAuthentication,)


class UserSettings(APIView):
    authentication_classes = (JwtAuthentication,)

    def get(self, request):
        """
        View a user's app settings.
        ---
        response_serializer: user.serializers.UserSettingSerializer
        """
        user_settings = UserSetting.objects.filter(user=request.user)
        settings = Setting.objects.all()

        settings_list = []

        for setting in settings:
            user_setting = user_settings.filter(setting=setting).first()

            if not user_setting:
                user_setting = UserSetting(
                    user=request.user,
                    setting=setting,
                    value=setting.default_value,
                )
                is_user_defined = False
            else:
                is_user_defined = True

            data = {'is_user_defined': is_user_defined}
            data.update(UserSettingSerializer(user_setting).data)
            data.update(SettingSerializer(setting).data)
            settings_list.append(data)

        return Response(settings_list)

    def put(self, request):
        """
        Change a user's app settings. Takes one or more slug-value pairs.
        Responds with a 204 - No Content.
        ---
        request_serializer: user.serializers.UpdateUserSettingSerializer
        responseMessages:
            - code: 400
              message: Some of the given settings are invalid.
        """
        bad_settings = self._filter_bad_setting_slugs(request.data)

        if bad_settings:
            return Response({
                'error': 'Some of the given settings are invalid.',
                'messages': bad_settings
            }, HTTP_400_BAD_REQUEST)

        validation_errors = []

        for slug_key, value in request.data.items():
            user_setting = self._create_or_update_user_setting(request.user, slug_key, value)
            try:
                user_setting.full_clean()
            except ValidationError as e:
                validation_errors.extend(e.messages)
            else:
                user_setting.save()
                if slug_key in intercom_api.USER_CUSTOM_ATTRIBUTES:
                    try:
                        intercom_api.update_user_custom_attribute(settings.INTERCOM_TOKEN, request.user.uid,
                                                                  slug_key, value)
                    except intercom_api.IntercomException:
                        pass

        if validation_errors:
            return Response({
                'error': 'Some of the given settings are invalid.',
                'messages': validation_errors,
            }, HTTP_400_BAD_REQUEST)

        return Response(status=HTTP_204_NO_CONTENT)

    def delete(self, request):
        """
        Reset a user's app settings.
        Responds with a 204 - No Content.
        """
        UserSetting.objects.filter(user=request.user).delete()
        try:
            intercom_api.reset_user_custom_attributes(settings.INTERCOM_TOKEN, request.user.uid)
        except intercom_api.IntercomException:
            pass

        return Response(status=HTTP_204_NO_CONTENT)

    @staticmethod
    def _filter_bad_setting_slugs(request_data):
        bad_settings = []

        for k, v in request_data.items():
            setting = Setting.objects.filter(slug=k).first()
            if not setting:
                bad_settings.append(k)

        return bad_settings

    @staticmethod
    def _create_or_update_user_setting(user, setting_slug, value):
        user_setting = UserSetting.objects.filter(user=user, setting__slug=setting_slug).first()
        if user_setting:
            user_setting.value = value
        else:
            setting = Setting.objects.filter(slug=setting_slug).first()
            user_setting = UserSetting(user=user, setting=setting, value=value)
        return user_setting


class IdentifyApplicationKit(APIView):
    """
    App "phonehome" logic. If a ClientApplication is not paired with a known
    kit_name, an 'invalid' ApplicationKit object is created for tracking.
    """
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = ApplicationKitSerializer
    model = ClientApplicationKit

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            client_id = valid_data['client_id']
            if ClientApplication.objects.filter(client_id=client_id).exists():
                query = {
                    'client_id': client_id,
                    'kit_name': valid_data['kit_name'].lower(),
                }
                app_kit, is_created = self.model.objects.get_or_create(**query)
                if is_created:
                    app_kit.is_valid = False
                    app_kit.save()

        return Response({}, HTTP_200_OK)

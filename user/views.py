import base64
import hashlib
import logging
from datetime import datetime
from typing import Tuple

import arrow
import jwt
import requests
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.core.cache import cache
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.http import Http404
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from mail_templated import send_mail
from requests_oauthlib import OAuth1Session
from rest_framework import mixins, exceptions
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import (CreateAPIView, GenericAPIView, ListAPIView, RetrieveAPIView,
                                     RetrieveUpdateAPIView, get_object_or_404)
from rest_framework.mixins import UpdateModelMixin
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import (HTTP_200_OK, HTTP_204_NO_CONTENT,
                                   HTTP_400_BAD_REQUEST)
from rest_framework.views import APIView

import analytics
from errors import (FACEBOOK_CANT_VALIDATE, FACEBOOK_GRAPH_ACCESS, FACEBOOK_INVALID_USER,
                    INCORRECT_CREDENTIALS, REGISTRATION_FAILED, error_response)
from history.signals import HISTORY_CONTEXT
from history.utils import user_info
from magic_link.tasks import send_magic_link
from prometheus.metrics import service_creation_counter
from scheme.credentials import EMAIL
from scheme.models import SchemeAccount, SchemeAccountCredentialAnswer
from ubiquity.channel_vault import get_jwt_secret
from ubiquity.models import SchemeAccountEntry
from ubiquity.versioning.base.serializers import ServiceSerializer
from user.authentication import JwtAuthentication
from user.exceptions import MagicLinkValidationError, MagicLinkExpiredTokenError
from user.models import (ClientApplication, ClientApplicationKit, CustomUser, Setting, UserSetting, valid_reset_code,
                         BINK_APP_ID)
from user.serializers import (ApplicationKitSerializer, FacebookRegisterSerializer, LoginSerializer, NewLoginSerializer,
                              NewRegisterSerializer, ApplyPromoCodeSerializer, RegisterSerializer,
                              ResetPasswordSerializer, ResetTokenSerializer, ResponseAuthSerializer, SettingSerializer,
                              TokenResetPasswordSerializer, TwitterRegisterSerializer, UserSerializer,
                              UserSettingSerializer, AppleRegisterSerializer, MakeMagicLinkSerializer)

logger = logging.getLogger(__name__)


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
            channel = serializer.validated_data['bundle_id']
            HISTORY_CONTEXT.user_info = user_info(user_id=None, channel=channel)

            serializer.save()
            service_creation_counter.labels(
                channel=channel
            ).inc()
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
            send_mail(
                'email.tpl',
                {
                    'link': '{}/{}'.format(settings.LETHE_URL, user.reset_token),
                    'hermes_url': settings.MEDIA_URL
                },
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False
            )

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

        bundle_id = request.POST.get('bundle_id', '')

        if not user:
            return error_response(INCORRECT_CREDENTIALS)

        HISTORY_CONTEXT.user_info = user_info(
            user_id=user.id,
            channel=serializer.validated_data.get('bundle_id', "internal_service")
        )

        login(request, user)
        out_serializer = ResponseAuthSerializer({'email': user.email,
                                                 'api_key': user.create_token(bundle_id),
                                                 'uid': user.uid
                                                 })
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
        email = request.data.get('email', None)
        client_id = request.data.get('client_id', BINK_APP_ID)
        r = requests.get("https://graph.facebook.com/me?access_token={0}".format(access_token))
        if not r.ok:
            return error_response(FACEBOOK_CANT_VALIDATE)
        if r.json()['id'] != user_id.strip():
            return error_response(FACEBOOK_INVALID_USER)
        return facebook_login(access_token, email, client_id)


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


class AppleLogin(GenericAPIView):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)

    serializer_class = AppleRegisterSerializer

    def post(self, request, *args, **kwargs):
        """
        Login using an Apple account.
        ---
        response_serializer: ResponseAuthSerializer
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return apple_login(code=serializer.validated_data["authorization_code"])


class Renew(APIView):

    def post(self, request, *args, **kwargs):
        auth = JwtAuthentication()
        token, token_type = auth.get_token_type(request)
        if token_type != b'token':
            return Response({'error': "Invalid Token"}, status=400)

        user, token_contents = auth.authenticate_credentials(token)
        bundle_id = token_contents.get('bundle_id', '')

        if not user.email:
            raise exceptions.AuthenticationFailed(_('User does not have an email address'))

        # Note create_token will try to get bundle_id if not set.
        try:
            new_token = user.create_token(bundle_id)
        except MultipleObjectsReturned:
            raise exceptions.AuthenticationFailed(_("No bundle_id in token and multiple bundles defined for this user"))

        return Response({'api_key': new_token})


class Logout(APIView):
    def post(self, request, *args, **kwargs):
        request.user.generate_salt()
        request.user.save()
        return Response({'logged_out': True})


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


def facebook_login(access_token, user_email=None, client_id=BINK_APP_ID):
    params = {"access_token": access_token, "fields": "email,name,id"}
    # Retrieve information about the current user.
    r = requests.get('https://graph.facebook.com/me', params=params)
    if not r.ok:
        return error_response(FACEBOOK_GRAPH_ACCESS)
    profile = r.json()
    # Email from client over-rides the facebook one
    if not user_email:
        user_email = profile.get('email')
    return social_response(profile['id'], user_email, 'facebook', client_id)


def twitter_login(access_token, access_token_secret, client_id=BINK_APP_ID):
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
    return social_response(profile['id_str'], email, 'twitter', client_id)


def generate_apple_client_secret():
    time_now = datetime.utcnow().timestamp()

    headers = {
        "kid": settings.APPLE_KEY_ID
    }
    claims = {
        "iss": settings.APPLE_TEAM_ID,
        "aud": "https://appleid.apple.com",
        "sub": settings.APPLE_APP_ID,
        "iat": time_now,
        "exp": time_now + 86400 * 180,
    }

    key = base64.b64decode(settings.APPLE_CLIENT_SECRET).decode("utf-8")
    client_secret = jwt.encode(
        payload=claims,
        key=key,
        headers=headers,
        algorithm="ES256",
    )

    return client_secret


def apple_login(code):
    url = "https://appleid.apple.com/auth/token"
    grant_type = "authorization_code"
    headers = {"content-type": "application/x-www-form-urlencoded"}
    # this is confusing client id is set to the bundle id which defaults in settings to com.bink.wallet
    # the call to social_response will assume BINK_APP_ID which is the only client_id mapping to com.bink.wallet
    # todo fix APPLE_APP_ID in settings it should have been client id not bundle id so do we do a lookup or add another
    # settings value. The answer depends on how we will manage client ids.
    params = {
        "client_id": settings.APPLE_APP_ID,
        "client_secret": generate_apple_client_secret(),
        "code": code,
        "grant_type": grant_type
    }

    resp = requests.post(url, data=params, headers=headers)

    if not resp.ok:
        logger.error(
            f"Apple Sign In failed - response: {resp.json()}"
        )

    resp.raise_for_status()

    id_token = resp.json()["id_token"]
    user_info = jwt.decode(id_token, options={"verify_signature": False}, algorithms=['HS512', 'HS256'])

    logger.info("Successful Apple Sign In")
    return social_response(
        social_id=user_info["sub"],
        email=user_info["email"],
        service="apple",
    )


def social_response(social_id, email, service, client_id=BINK_APP_ID):
    status, user = social_login(social_id, email, service, client_id)

    out_serializer = ResponseAuthSerializer({'email': user.email, 'api_key': user.create_token(), 'uid': user.uid})
    return Response(out_serializer.data, status=status)


def social_login(social_id, email, service, client_id=BINK_APP_ID):
    status = 200
    try:
        # By default the user is always set to user models BINK_APP_ID therefore provided client_id is also set to same
        # default we will always find users which were created before the change to search for client_id
        # Note client id  is same as client__client_id because client_id is a primary index
        user = CustomUser.objects.get(**{service: social_id, 'client_id': client_id})
        if not user.email and email:
            user.email = email
            user.save()
    except CustomUser.DoesNotExist:
        try:
            if not email:
                raise CustomUser.DoesNotExist
            # User exists in our system but hasn't been linked
            # Before we tested for client_id it is possible we linked users with a different client_id
            # that user should not have been linked to a service and a new user created in BINK_APP_ID
            user = CustomUser.objects.get(email__iexact=email, client_id=client_id)
            setattr(user, service, social_id)
            user.save()
        except CustomUser.DoesNotExist:
            # We are creating a new user
            password = get_random_string(length=32)
            user = CustomUser.objects.create_user(**{'email': email, 'password': password, service: social_id,
                                                     'client_id': client_id})
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
                if slug_key in analytics.SETTING_CUSTOM_ATTRIBUTES:

                    attributes = {
                        slug_key: user_setting.to_boolean()
                    }
                    if request.user.client_id == settings.BINK_CLIENT_ID:
                        analytics.update_attributes(request.user, attributes)

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
        if request.user.client_id == settings.BINK_CLIENT_ID:
            analytics.reset_user_settings(request.user)

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


class OrganisationTermsAndConditions(RetrieveAPIView):
    """
        Gets terms and conditions as HTML and returns a JSON object
    """
    authentication_classes = (JwtAuthentication,)

    def get(self, request, *args, **kwargs):
        user = get_object_or_404(CustomUser, id=request.user.id)
        terms_and_conditions = user.client.organisation.terms_and_conditions

        return Response({
            'terms_and_conditions': terms_and_conditions,
        }, status=200)


class MagicLinkAuthView(CreateAPIView):
    """
    Exchange a magic link temporary token for a new or existing user's authorisation token.
    """
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)

    @staticmethod
    def auto_add_membership_cards_with_email(user, bundle_id):
        """
        Auto add loyalty card when user auth with magic link. Checks for schemes that have email as
        an auth field.
        """

        # LOY-1609 - we only want to do this for wasabi for for now until later on.
        # Remove this when we want to open this up for all schemes.
        if bundle_id == 'com.wasabi.bink.web':
            # Make sure scheme account is authorised with the same email in the magic link
            scheme_account_ids = SchemeAccountCredentialAnswer.objects.filter(
                question__type=EMAIL,
                question__auth_field=True,
                scheme_account__scheme__slug="wasabi-club",
                scheme_account__status=SchemeAccount.ACTIVE,
                answer=user.email
            ).values_list('scheme_account__pk', flat=True)

            entries_to_create = [
                SchemeAccountEntry(
                    scheme_account_id=scheme_account_id,
                    user_id=user.id,
                ) for scheme_account_id in scheme_account_ids
            ]

            if entries_to_create:
                SchemeAccountEntry.objects.bulk_create(entries_to_create)

    @staticmethod
    def _get_jwt_secret(token: str) -> str:
        try:
            bundle_id = jwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=['HS512', 'HS256']
            )["bundle_id"]
            jwt_secret = get_jwt_secret(bundle_id)
        except (KeyError, jwt.DecodeError, AuthenticationFailed):
            logger.debug("failed to extract bundle_id from magic link temporary token.")
            raise MagicLinkValidationError

        return jwt_secret

    def _validate_token(self, token: str) -> Tuple[str, str, str, int]:
        """
        :param token: magic link temporary token
        :return: email, bundle_id, md5 token hash, remaining token validity time in seconds
        """

        if not token:
            logger.debug("failed to provide a magic link temporary token.")
            raise MagicLinkValidationError

        token_secret = self._get_jwt_secret(token)

        token_hash = hashlib.md5(token.encode()).hexdigest()
        if cache.get(f"ml:{token_hash}"):
            logger.debug("magic link temporary token has already been used.")
            raise MagicLinkExpiredTokenError

        try:
            token_data = jwt.decode(
                token,
                token_secret,
                algorithms=['HS512', 'HS256']
            )
            email = token_data["email"]
            bundle_id = token_data["bundle_id"]
            exp = int(token_data["exp"])

        except jwt.ExpiredSignatureError:
            logger.debug("magic link temporary token has expired.")
            raise MagicLinkExpiredTokenError

        except (KeyError, ValueError, jwt.DecodeError) as e:
            if type(e) in (KeyError, ValueError):
                message = ("the provided magic link temporary token was signed correctly "
                           "but did not contain the required information.")

            else:
                message = ("the provided magic link temporary token was not signed correctly "
                           "or was not in a valid format")

            logger.debug(message)
            raise MagicLinkValidationError

        return email, bundle_id, token_hash, exp - arrow.utcnow().timestamp

    def create(self, request, *args, **kwargs):
        tmp_token = request.data.get("token")
        email, bundle_id, token_hash, valid_for = self._validate_token(tmp_token)

        client_id = ClientApplication.objects.values_list("pk", flat=True).filter(
            clientapplicationbundle__bundle_id=bundle_id
        ).first()

        if not client_id:
            logger.debug(f"bundle_id: '{bundle_id}' provided in the magic link temporary token is not valid.")
            raise MagicLinkValidationError

        HISTORY_CONTEXT.user_info = user_info(user_id=None, channel=bundle_id)

        try:
            user = CustomUser.objects.get(email__iexact=email, client_id=client_id)
        except CustomUser.DoesNotExist:
            user = ServiceSerializer.create_new_user(
                client_id=client_id,
                bundle_id=bundle_id,
                email=email,
                external_id=None,
            )

            # Auto add membership cards that has been authorised and using the same email
            # We only want to do this once when the user is created
            self.auto_add_membership_cards_with_email(user, bundle_id)

        if not user.magic_link_verified:
            user.magic_link_verified = datetime.utcnow()
            user.save(update_fields=["magic_link_verified"])

        cache.set(f"ml:{token_hash}", True, valid_for + 1)
        token = user.create_token(bundle_id)
        return Response({"access_token": token})


def call_send_magic_link(email, url, email_from, subject, expiry_date, bundle_id, expiry, token, external_name,
                         slug="", locale=""):
    """
    This is function is required for testing and call send_magic_link when implemented
    :param email: Email account to send email to
    :param url: Magic link url
    :param email_from: Email account from which the magic link is displayed as being sent from
    :param subject: Email subject line
    :param expiry_date:
    :param bundle_id:
    :param expiry:
    :param token:
    :param external_name:   external channel name used in template from  external_name.bink.com
    :param slug: not used identifies the scheme
    :param locale: may be used in future templates for internationalisation
    :param
    """

    send_magic_link.delay(email, email_from, subject, token, url, external_name, expiry_date, slug, bundle_id)


class MakeMagicLink(APIView):
    authentication_classes = (OpenAuthentication,)
    permission_classes = (AllowAny,)
    serializer_class = MakeMagicLinkSerializer

    @method_decorator(csrf_exempt)
    def post(self, request):
        """
        Make a magic link and send it in a user email
        ---
        type:

            email:
                required: true
                type: json
            slug:
                required: true
                type: json
            locale:
                required: true
                type: json
            bundle_id:
                required: true
                type: json
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            call_send_magic_link(**serializer.validated_data)
            r_status = HTTP_200_OK
            message = "Successful"
        else:
            r_status = HTTP_400_BAD_REQUEST
            error = serializer.errors
            if error.get('email'):
                message = "Bad email parameter"
            else:
                message = "Bad request parameter"
            logger.info(f"Make Magic Links Error: {serializer.errors}")

        return Response(message, r_status)

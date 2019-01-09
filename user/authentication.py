import jwt
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils.translation import ugettext_lazy as _
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.permissions import BasePermission
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from user.models import CustomUser, ClientApplicationBundle


class JwtAuthentication(BaseAuthentication):
    """
    Simple token based authentication.

    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string "Token ".  For example:

        Authorization: Token 401f7ac837da42b97f613d789819ff93537bee6a
    """

    model = CustomUser
    """
    A custom token model may be used, but must have the following properties.

    * key -- The string identifying the token
    * user -- The user to which the token belongs
    """

    @staticmethod
    def get_token(request, token_name=b'token'):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != token_name:
            return None

        if len(auth) == 1:
            msg = _('Invalid token header. No credentials provided.')
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = _('Invalid token header. Token string should not contain spaces.')
            raise exceptions.AuthenticationFailed(msg)

        try:
            token = auth[1].decode()
        except UnicodeError:
            msg = _('Invalid token header. Token string should not contain invalid characters.')
            raise exceptions.AuthenticationFailed(msg)
        return token

    def authenticate(self, request):
        token = self.get_token(request)
        # If its not a JWT token return none
        if not token or "." not in token:
            return None

        user, credentials = self.authenticate_credentials(token)
        # Finds the bundle_id from login2 assuming the user has logged in post upgrade
        # otherwise 'com.bink.wallet' will be used for the the users application client
        # this will fail if no 'com.bink.wallet' exists or if multiple matches are found
        bundle_id = credentials.get('bundle_id', 'com.bink.wallet')
        try:
            bundle = ClientApplicationBundle.objects.get(bundle_id=bundle_id, client=user.client)
        except ObjectDoesNotExist:
            raise exceptions.AuthenticationFailed('Bundle Id not configured')
        except MultipleObjectsReturned:
            # This should not occur after release as unique together constraint has been added in a migration
            # Covers edge case of duplicate already exists which would cause the unique together migration to fail
            # then this error message will help debug
            raise exceptions.AuthenticationFailed(f"Multiple '{bundle_id}' bundle ids for client '{user.client}'")

        setattr(request, 'allowed_issuers', [issuer.pk for issuer in bundle.issuers.all()])
        setattr(request, 'allowed_schemes', [scheme.pk for scheme in bundle.schemes.all()])
        return user, None

    def authenticate_credentials(self, key):
        """
        Verify the JWT by first extracting the User ID, then obtaining
        the corresponding ClientApplication secret value.

        Returns CustomUser instance.
        """
        try:
            token_contents = jwt.decode(
                key,
                verify=False,
                leeway=settings.CLOCK_SKEW_LEEWAY)
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        try:
            user = self.model.objects.get(id=token_contents['sub'])

        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('User does not exist.'))

        try:
            jwt.decode(
                key,
                user.client.secret + user.salt,
                verify=True,
                leeway=settings.CLOCK_SKEW_LEEWAY)
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))
        return user, token_contents

    def authenticate_header(self, request):
        return 'Token'


class ServiceUser(AnonymousUser):
    def is_authenticated(self):
        return True

    uid = 'api_user'


class ServiceAuthentication(JwtAuthentication):
    """
    Authentication for olympus services
    """

    def authenticate_credentials(self, key):
        if key != settings.SERVICE_API_KEY:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))
        return ServiceUser(), None

    def authenticate(self, request):
        return self.authenticate_credentials(self.get_token(request))


class AllowService(BasePermission):
    def has_permission(self, request, view):
        return request.user.uid == 'api_user'

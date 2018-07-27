import jwt
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils.translation import ugettext_lazy as _
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.permissions import BasePermission

from user.models import CustomUser


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

        user, _ = self.authenticate_credentials(token)
        setattr(request, 'allowed_issuers', [issuer.pk for issuer in user.client.organisation.issuers.all()])
        setattr(request, 'allowed_schemes', [scheme.pk for scheme in user.client.organisation.schemes.all()])
        return user, _

    def authenticate_credentials(self, key):
        """
        Verify the JWT by first extracting the User ID, then obtaining
        the corresponding ClientApplication secret value.

        Returns CustomUser instance.
        """
        try:
            token_contents = jwt.decode(key, verify=False)
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        try:
            user = self.model.objects.get(id=token_contents['sub'])

        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('User does not exist.'))

        try:
            jwt.decode(key, user.client.secret + user.salt, verify=True)
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))
        return user, None

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

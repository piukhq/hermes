from rest_framework.authentication import BaseAuthentication, get_authorization_header
from django.utils.translation import ugettext_lazy as _
from rest_framework.permissions import BasePermission
from user.models import CustomUser
from rest_framework import exceptions
import jwt
from django.conf import settings


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

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'token':
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

        return self.authenticate_credentials(token)

    def authenticate_credentials(self, key):
        try:
            token_contents = jwt.decode(key, settings.TOKEN_SECRET)
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        try:
            token = self.model.objects.get(id=token_contents['sub'])
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('User does not exist.'))

        return token, token

    def authenticate_header(self, request):
        return 'Token'


class ServiceAuthentication(JwtAuthentication):
    """
    Authentication for olympus services
    """
    def authenticate_credentials(self, key):
        if key != settings.SERVICE_API_KEY:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))
        user = "api_user"
        return user, None


class AllowService(BasePermission):
    def has_permission(self, request, view):
        return request.user == 'api_user'

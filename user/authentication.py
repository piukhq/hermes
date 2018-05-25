from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from django.utils.translation import ugettext_lazy as _
from rest_framework.permissions import BasePermission
from user.models import Property
from rest_framework import exceptions
import jwt
from django.conf import settings


class JwtAuthentication(BaseAuthentication):
    model = Property

    @staticmethod
    def get_token(request):
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
        return token

    def authenticate(self, request):
        token = self.get_token(request)
        # If its not a JWT token return none
        if not token or "." not in token:
            return None
        prop, auth = self.authenticate_credentials(token)
        setattr(request, 'prop', prop)
        return prop, auth

    def authenticate_credentials(self, key):
        try:
            token_contents = jwt.decode(key, verify=False)
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        try:
            prop = self.model.objects.get(uid=token_contents['sub'])
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('Property does not exist.'))

        try:
            jwt.decode(key, prop.client.secret + prop.salt, verify=True)
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))
        return prop, None

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

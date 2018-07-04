import jwt
from django.utils.translation import ugettext_lazy as _
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

from user.authentication import JwtAuthentication
from user.models import ClientApplication


class PropertyAuthentication(JwtAuthentication):
    model = ClientApplication
    expected_fields = []

    def authenticate_credentials(self, token):
        try:
            organisation_id = jwt.decode(token, verify=False, algorithms=['HS512'])['Organization ID']
            client = self.model.objects.get(client_id=organisation_id)
            email = jwt.decode(token, client.secret, verify=True, algorithms=['HS512'])['Email']
        except (jwt.DecodeError, KeyError, self.model.DoesNotExist):
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        return client, email

    def authenticate(self, request):
        token = self.get_token(request)
        if not token or "." not in token:
            return None

        client_app, email = self.authenticate_credentials(token)
        setattr(request, 'client_app', client_app)
        setattr(request, 'prop_email', email)
        return client_app, None


class PropertyOrJWTAuthentication(BaseAuthentication):

    def authenticate(self, request):
        if request.method == 'DELETE':
            return JwtAuthentication().authenticate(request)

        return PropertyAuthentication().authenticate(request)

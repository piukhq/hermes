import jwt
from django.utils.translation import ugettext_lazy as _
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

from user.authentication import JwtAuthentication
from user.models import ClientApplicationBundle, CustomUser


class ServiceRegistrationAuthentication(JwtAuthentication):
    model = ClientApplicationBundle
    expected_fields = []

    def authenticate_credentials(self, token):
        try:
            token_data = jwt.decode(token, verify=False, algorithms=['HS512'])
            bundle_id = token_data['Bundle ID']
            organisation_id = token_data['Organisation ID']
            bundle = self.model.objects.get(bundle_id=bundle_id)
            if bundle.client.client_id != organisation_id:
                raise KeyError

            email = jwt.decode(token, bundle.client.secret, verify=True, algorithms=['HS512'])['Email']
        except (jwt.DecodeError, KeyError, self.model.DoesNotExist):
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        return bundle, email

    def authenticate(self, request):
        token = self.get_token(request, b'bearer')
        if not token or "." not in token:
            return None

        bundle, email = self.authenticate_credentials(token)
        setattr(request, 'bundle', bundle)
        setattr(request, 'prop_email', email)
        return bundle, None


class PropertyAuthentication(ServiceRegistrationAuthentication):
    def authenticate(self, request):
        token = self.get_token(request, b'bearer')
        if not token or "." not in token:
            return None

        bundle, email = self.authenticate_credentials(token)
        try:
            user = CustomUser.objects.get(email='{}__{}'.format(bundle.bundle_id, email))
        except CustomUser.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        setattr(request, 'allowed_issuers', [issuer.pk for issuer in user.client.organisation.issuers.all()])
        setattr(request, 'allowed_schemes', [scheme.pk for scheme in user.client.organisation.schemes.all()])
        return user, None


class PropertyOrServiceAuthentication(BaseAuthentication):

    def authenticate(self, request):
        if request.method == 'POST':
            return ServiceRegistrationAuthentication().authenticate(request)

        return PropertyAuthentication().authenticate(request)

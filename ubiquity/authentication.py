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
            bundle_id = token_data['bundle_id']
            organisation_id = token_data['organisation_id']
            bundle = self.model.objects.get(bundle_id=bundle_id)
            if bundle.client.organisation.name != organisation_id:
                raise KeyError

            external_id = jwt.decode(token, bundle.client.secret, verify=True, algorithms=['HS512'])['user_id']
        except (jwt.DecodeError, KeyError, self.model.DoesNotExist):
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        return bundle, external_id

    def authenticate(self, request):
        token = self.get_token(request, b'bearer')
        if not token or "." not in token:
            return None

        bundle, external_id = self.authenticate_credentials(token)
        setattr(request, 'bundle', bundle)
        setattr(request, 'prop_id', external_id)
        return bundle, None


class PropertyAuthentication(ServiceRegistrationAuthentication):
    def authenticate(self, request):
        token = self.get_token(request, b'bearer')
        if not token or "." not in token:
            return None

        bundle, external_id = self.authenticate_credentials(token)
        try:
            user = CustomUser.objects.get(external_id=external_id, client=bundle.client)
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

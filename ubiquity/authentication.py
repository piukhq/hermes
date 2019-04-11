import jwt
from django.utils.translation import ugettext_lazy as _
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import NotFound
from hermes.channels import Permit
from user.authentication import JwtAuthentication
from user.models import ClientApplicationBundle, CustomUser


class ServiceRegistrationAuthentication(JwtAuthentication):
    expected_fields = []

    def authenticate_credentials(self, token):
        try:
            token_data = jwt.decode(token, verify=False, algorithms=['HS512'])
            bundle_id = token_data['bundle_id']
            organisation_id = token_data['organisation_id']
            channels_permit = Permit(bundle_id, organisation_name=organisation_id, ubiquity=True)

            if not(token_data.get('property_id') and token_data.get('iat')):
                raise KeyError    # We can't implement a timeout as token refresh not in spec.

            external_id = jwt.decode(token, channels_permit.bundle.client.secret,
                                     verify=True, algorithms=['HS512'])['user_id']
        except (jwt.DecodeError, KeyError, self.model.DoesNotExist):
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        if not external_id:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        return channels_permit, external_id

    def authenticate(self, request):
        token = self.get_token(request, b'bearer')
        if not token or "." not in token:
            return None

        channels_permit, external_id = self.authenticate_credentials(token)
        setattr(request, 'channels_permit', channels_permit)
        setattr(request, 'prop_id', external_id)
        return channels_permit, None


class ServiceAuthentication(ServiceRegistrationAuthentication):
    model = ClientApplicationBundle
    expected_fields = []

    def authenticate(self, request):
        token = self.get_token(request, b'bearer')
        if not token or "." not in token:
            return None

        channels_permit, external_id = self.authenticate_credentials(token)

        try:
            user = CustomUser.objects.get(external_id=external_id, client=channels_permit.bundle.client, is_active=True)
        except CustomUser.DoesNotExist:
            raise NotFound

        setattr(request, 'channels_permit', channels_permit)
        setattr(request, 'prop_id', external_id)
        return user, None


class PropertyAuthentication(ServiceRegistrationAuthentication):
    def authenticate(self, request):
        token = self.get_token(request, b'bearer')
        if not token or "." not in token:
            return None

        channels_permit, external_id = self.authenticate_credentials(token)
        try:
            user = CustomUser.objects.get(external_id=external_id, client=channels_permit.bundle.client, is_active=True)
        except CustomUser.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        setattr(request, 'allowed_issuers', [issuer.pk for issuer in channels_permit.bundle.issuer.all()])
        setattr(request, 'channels_permit', channels_permit)
        return user, None


class PropertyOrServiceAuthentication(BaseAuthentication):

    def authenticate(self, request):
        if request.method == 'POST':
            return ServiceRegistrationAuthentication().authenticate(request)

        return ServiceAuthentication().authenticate(request)

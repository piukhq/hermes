import logging
import time

import jwt
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.generics import get_object_or_404

from hermes.channels import Permit
from user.authentication import JwtAuthentication
from user.models import ClientApplicationBundle, CustomUser

logger = logging.getLogger(__name__)


class ServiceRegistrationAuthentication(JwtAuthentication):
    expected_fields = []

    def authenticate_request(self, request):
        token, token_type = self.get_token_type(request)
        if not token or "." not in token:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))
        return self.authenticate_credentials(token, token_type)

    def user_authenticate(self, request, no_user_error):
        channels_permit, auth_user_id = self.authenticate_request(request)

        if channels_permit.user:
            if not channels_permit.user.is_active:
                raise NotFound
        else:
            try:
                channels_permit.user = CustomUser.objects.get(
                    external_id=auth_user_id, client=channels_permit.bundle.client)
            except CustomUser.DoesNotExist:
                raise no_user_error

        return channels_permit, auth_user_id

    def authenticate_credentials(self, token, token_type=""):
        try:
            token_data = jwt.decode(token, verify=False, algorithms=['HS512', 'HS256'])
            bundle_id = token_data['bundle_id']
            if token_type == b'bearer':
                channels_permit, auth_user_id = self._authenticate_bearer(token, token_data, bundle_id)
            elif token_type == b'token':
                channels_permit, auth_user_id = self._authenticate_token(token, token_data, bundle_id, auth_by='bink')
            else:
                raise exceptions.AuthenticationFailed(_('Unknown token.'))

        except (jwt.DecodeError, KeyError, self.model.DoesNotExist):
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        if not auth_user_id:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        return channels_permit, auth_user_id

    def authenticate(self, request):
        channels_permit, auth_user_id = self.authenticate_request(request)
        setattr(request, 'channels_permit', channels_permit)
        setattr(request, 'prop_id', auth_user_id)
        return channels_permit, None

    @staticmethod
    def _authenticate_bearer(token, token_data, bundle_id):
        organisation_id = token_data['organisation_id']
        channels_permit = Permit(bundle_id, organisation_name=organisation_id, ubiquity=True)
        # Check for keys which should be in token but don't cause a failed token or raise a key error
        if 'property_id' not in token_data:
            logger.info('No property id found in Ubiquity token')
        if 'iat' not in token_data:
            # We can't implement a timeout as token refresh not in spec.
            logger.info('No iat (time stamp) found in Ubiquity token')

        if bundle_id == settings.INTERNAL_SERVICE_BUNDLE:
            if 'iat' not in token_data:
                raise exceptions.AuthenticationFailed(_('No iat for internal service JWT'))
            if token_data['iat'] < time.time() - settings.JWT_EXPIRY_TIME:
                raise exceptions.AuthenticationFailed(_('Expired token.'))

        auth_user_id = jwt.decode(token, channels_permit.bundle.client.secret,
                                  leeway=settings.CLOCK_SKEW_LEEWAY,
                                  verify=True, algorithms=['HS512'])['user_id']
        return channels_permit, auth_user_id

    @staticmethod
    def _authenticate_token(token, token_data, bundle_id, auth_by):
        # This is the client server token with "token" prefix
        user = get_object_or_404(CustomUser.objects, id=token_data['sub'])
        channels_permit = Permit(bundle_id, user=user, ubiquity=True, auth_by=auth_by)

        if not user.email:
            logger.info("'token' type token does not have an email address")
            raise exceptions.AuthenticationFailed(_('Invalid token'))
        if 'iat' not in token_data:
            logger.info("'token' type token does not a time stamp 'iat'' field")
            raise exceptions.AuthenticationFailed(_('Invalid token'))

        jwt.decode(token, channels_permit.bundle.client.secret + channels_permit.user.salt,
                   leeway=settings.CLOCK_SKEW_LEEWAY,
                   verify=True, algorithms=['HS256', 'HS512'])
        auth_user_id = channels_permit.user.email

        return channels_permit, auth_user_id


class ServiceAuthentication(ServiceRegistrationAuthentication):
    model = ClientApplicationBundle
    expected_fields = []

    def authenticate(self, request):
        # authenticate user raising NotFound error if user does not exist.  This is the expected error get Service
        # end point which causes a Not Found message to indicate that the Service had not been posted
        channels_permit, auth_user_id = self.user_authenticate(request, NotFound)
        setattr(request, 'channels_permit', channels_permit)
        setattr(request, 'prop_id', auth_user_id)
        return channels_permit.user, None


class PropertyAuthentication(ServiceRegistrationAuthentication):

    def authenticate(self, request):
        # authenticate user raising Invalid token if user does not exist.  This is the expected error for all
        # non service end points.
        channels_permit, auth_user_id = self.user_authenticate(request,
                                                               exceptions.AuthenticationFailed(_('Invalid token.')))
        setattr(request, 'channels_permit', channels_permit)
        return channels_permit.user, None


class PropertyOrServiceAuthentication(BaseAuthentication):

    def authenticate(self, request):
        if request.method == 'POST':
            return ServiceRegistrationAuthentication().authenticate(request)

        return ServiceAuthentication().authenticate(request)

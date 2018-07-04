import uuid

import arrow
from rest_framework import status
from rest_framework.exceptions import ParseError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from ubiquity.authentication import PropertyOrJWTAuthentication
from ubiquity.models import ServiceConsent
from user.models import CustomUser
from user.serializers import RegisterSerializer


class ServiceView(APIView):
    authentication_classes = (PropertyOrJWTAuthentication,)
    serializer = RegisterSerializer
    model = CustomUser

    # todo is this secure?
    def get(self, request):
        user_data = {
            'client_id': request.client_app.pk,
            'email': request.prop_email,
            'uid': request.prop_email,
        }
        user = get_object_or_404(self.model, **user_data)
        return Response({'email': user_data['email'], 'reset_token': user.generate_reset_token()})

    def post(self, request):
        new_user_data = {
            'client_id': request.client_app.pk,
            'email': request.prop_email,
            'uid': request.prop_email,
            'password': str(uuid.uuid4()).lower().replace('-', 'A&')
        }

        new_user = self.serializer(data=new_user_data)
        new_user.is_valid(raise_exception=True)
        user = new_user.save()

        try:
            consent_data = {
                'latitude': request.data['latitude'],
                'longitude': request.data['longitude'],
                'timestamp': arrow.get(request.data['timestamp']).datetime,
                'user': user
            }
        except KeyError:
            raise ParseError

        ServiceConsent.objects.create(**consent_data)
        return Response(new_user.data)

    @staticmethod
    def delete(request):
        user = request.user
        consent = user.serviceconsent
        consent.delete()
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

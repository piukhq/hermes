import uuid

from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from ubiquity.authentication import PropertyOrJWTAuthentication
from ubiquity.serializers import ServiceConsentSerilizer
from user.models import CustomUser
from user.serializers import RegisterSerializer


class ServiceView(APIView):
    authentication_classes = (PropertyOrJWTAuthentication,)
    serializer = RegisterSerializer
    model = CustomUser

    # todo is this secure?
    def get(self, request):
        user_data = {
            'client_id': request.bundle.client.pk,
            'email': '{}__{}'.format(request.bundle.client.client_id, request.prop_email),
            'uid': request.prop_email,
        }
        user = get_object_or_404(self.model, **user_data)
        return Response({'email': user_data['email'], 'reset_token': user.generate_reset_token()})

    def post(self, request):
        new_user_data = {
            'client_id': request.bundle.client.pk,
            'email': '{}__{}'.format(request.bundle.bundle_id, request.prop_email),
            'uid': request.prop_email,
            'password': str(uuid.uuid4()).lower().replace('-', 'A&')
        }

        new_user = self.serializer(data=new_user_data)
        new_user.is_valid(raise_exception=True)
        user = new_user.save()

        new_consent = ServiceConsentSerilizer(data={**request.data, 'user': user})
        new_consent.is_valid()
        errors = new_consent.errors

        # ServiceConsent.objects.create(**consent_data)
        return Response(new_user.data)

    @staticmethod
    def delete(request):
        user = request.user
        consent = user.serviceconsent
        consent.delete()
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

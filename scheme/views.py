from rest_framework import generics
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView, RetrieveAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from scheme.models import Scheme, SchemeAccount
from scheme.serializers import SchemeSerializer, SchemeAccountSerializer, SchemeAccountCredentialAnswer, \
    SchemeAccountAnswerSerializer
from rest_framework import status
from rest_framework.response import Response
from user.authenticators import UIDAuthentication


class SchemesList(generics.ListAPIView):
    queryset = Scheme.objects.filter(is_active=True)
    serializer_class = SchemeSerializer


class RetrieveScheme(RetrieveAPIView):
    queryset = Scheme.objects
    serializer_class = SchemeSerializer


class RetrieveUpdateDeleteAccount(RetrieveUpdateAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    serializer_class = SchemeAccountSerializer
    queryset = SchemeAccount.active_objects

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status = SchemeAccount.DELETED
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreateAccount(CreateAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    serializer_class = SchemeAccountSerializer


class CreateAnswer(CreateAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    serializer_class = SchemeAccountAnswerSerializer


class RetrieveUpdateDestroyAnswer(RetrieveUpdateDestroyAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    serializer_class = SchemeAccountAnswerSerializer
    queryset = SchemeAccountCredentialAnswer.objects

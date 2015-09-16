from rest_framework import generics
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView, RetrieveAPIView, RetrieveUpdateDestroyAPIView
from scheme.models import Scheme, SchemeAccount, SchemeAccountSecurityQuestion
from scheme.serializers import SchemeSerializer, SchemeAccountSerializer, SchemeAccountQuestionSerializer
from rest_framework import status
from rest_framework.response import Response


class SchemesList(generics.ListAPIView):
    queryset = Scheme.objects.filter(is_active=True)
    serializer_class = SchemeSerializer


class RetrieveScheme(RetrieveAPIView):
    queryset = Scheme.objects
    serializer_class = SchemeSerializer


class RetrieveUpdateDeleteAccount(RetrieveUpdateAPIView):
    serializer_class = SchemeAccountSerializer
    queryset = SchemeAccount.active_objects

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status = SchemeAccount.DELETED
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreateAccount(CreateAPIView):
    serializer_class = SchemeAccountSerializer


class CreateQuestion(CreateAPIView):
    serializer_class = SchemeAccountQuestionSerializer


class RetrieveUpdateDestroyQuestion(RetrieveUpdateDestroyAPIView):
    serializer_class = SchemeAccountQuestionSerializer
    queryset = SchemeAccountSecurityQuestion.objects
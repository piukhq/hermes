import json
from rest_framework import generics
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView, RetrieveAPIView,\
    RetrieveUpdateDestroyAPIView, get_object_or_404, ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from scheme.models import Scheme, SchemeAccount
from scheme.serializers import SchemeSerializer, SchemeAccountSerializer, SchemeAccountCredentialAnswer, \
    SchemeAccountAnswerSerializer, ListSchemeAccountSerializer
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

    def put(self, request, *args, **kwargs):
        scheme_account = get_object_or_404(SchemeAccount, user=request.user, id=kwargs['pk'])
        partial = kwargs.pop('partial', True)
        instance = scheme_account
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        response_data = {
            'id': scheme_account.id,
            'status': scheme_account.status,
            'order': scheme_account.order,
            'scheme_id': scheme_account.id,
        }
        for challenge in scheme_account.scheme.challenges:
            response = request.data[challenge.type]
            obj, created = SchemeAccountCredentialAnswer.objects.update_or_create(
                scheme_account=scheme_account, type=challenge.type, defaults={'answer': response})
            response_data[obj.type] = obj.answer
        return Response(json.dumps(response_data), content_type="application/json")

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status = SchemeAccount.DELETED
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreateAccount(ListCreateAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = SchemeAccountSerializer

    queryset = SchemeAccount.active_objects

    def post(self, request, *args, **kwargs):
        scheme = get_object_or_404(Scheme, pk=request.data['scheme'][0])
        scheme_account = SchemeAccount.objects.filter(scheme=scheme, user=request.user)
        if scheme_account:
            return Response(json.dumps({'Scheme Account': 'Scheme account exists'}),
                     status=status.HTTP_400_BAD_REQUEST,
                     content_type="application/json")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        scheme_account = get_object_or_404(SchemeAccount, scheme=scheme, user=request.user)
        response_data = {'id': scheme_account.id,
                         'scheme_id': scheme.id,
                         'order': scheme_account.order,
                         'status': scheme_account.status}
        for challenge in scheme.challenges:
            response = request.data[challenge.type]
            obj, created = SchemeAccountCredentialAnswer.objects.update_or_create(
                scheme_account=scheme_account, type=challenge.type, defaults={'answer': response})
            response_data[obj.type] = obj.answer
        return Response(json.dumps(response_data),
                        status=status.HTTP_201_CREATED,
                        headers=headers,
                        content_type="application/json")

    def list(self, request, *args, **kwargs):
        """
        Custom because we want a different serializer for reading
        """
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ListSchemeAccountSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ListSchemeAccountSerializer(queryset, many=True)
        return Response(serializer.data)


class CreateAnswer(CreateAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    serializer_class = SchemeAccountAnswerSerializer


class RetrieveUpdateDestroyAnswer(RetrieveUpdateDestroyAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    serializer_class = SchemeAccountAnswerSerializer
    queryset = SchemeAccountCredentialAnswer.objects

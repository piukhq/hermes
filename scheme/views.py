from rest_framework.generics import (CreateAPIView, RetrieveUpdateAPIView, RetrieveAPIView, ListAPIView, GenericAPIView,
                                     RetrieveUpdateDestroyAPIView, get_object_or_404, ListCreateAPIView)
from rest_framework.pagination import PageNumberPagination
from scheme.models import Scheme, SchemeAccount, SchemeAccountCredentialAnswer
from scheme.serializers import (SchemeSerializer, SchemeAccountAnswerSerializer,
                                ListSchemeAccountSerializer, UpdateSchemeAccountSerializer,
                                CreateSchemeAccountSerializer, GetSchemeAccountSerializer, StatusSerializer,
                                SchemeAccountCredentialsSerializer, SchemeAccountIdsSerializer)
from rest_framework import status
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.reverse import reverse
from user.authentication import ServiceAuthentication, AllowService
from django.db import transaction


class SwappableSerializerMixin(object):
    serializer_class = None
    override_serializer_classes = None

    def get_serializer_class(self):
        return self.override_serializer_classes[self.request.method]


class SchemesList(ListAPIView):
    queryset = Scheme.objects
    serializer_class = SchemeSerializer


class RetrieveScheme(RetrieveAPIView):
    queryset = Scheme.objects
    serializer_class = SchemeSerializer


class RetrieveUpdateDeleteAccount(SwappableSerializerMixin, RetrieveUpdateAPIView):
    override_serializer_classes = {
        'PUT': UpdateSchemeAccountSerializer,
        'PATCH': UpdateSchemeAccountSerializer,
        'GET': GetSchemeAccountSerializer,
        'DELETE': GetSchemeAccountSerializer,
        'OPTIONS': GetSchemeAccountSerializer,
    }

    queryset = SchemeAccount.active_objects

    def put(self, request, *args, **kwargs):
        scheme_account = get_object_or_404(SchemeAccount, user=request.user, id=kwargs['pk'])
        scheme = scheme_account.scheme
        # Check that the user doesnt have a scheme account with the primary question answer
        scheme_accounts = SchemeAccount.active_objects.filter(scheme=scheme, user=request.user)
        primary_question = scheme.primary_question

        for scheme_account in scheme_accounts.exclude(id=scheme_account.id):
            existing_primary_answer = scheme_account.primary_answer
            if existing_primary_answer and request.data[primary_question.type] == existing_primary_answer.answer:
                return json_error_response("A scheme account already exists with this {0}".format(
                    primary_question.label), status.HTTP_400_BAD_REQUEST)

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

        points = scheme_account.get_midas_balance()
        scheme_account.save()
        response_data['points'] = points

        # Pop scheme and user because these are the only two keys not related to questions
        request.data.pop('scheme', None)
        request.data.pop('user', None)
        if list(request.data.keys()) == [scheme.primary_question.type]:
            scheme_account.status = SchemeAccount.WALLET_ONLY
            scheme_account.save()

        response_data['status'] = scheme_account.status

        return Response(response_data)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreateAccount(SwappableSerializerMixin, ListCreateAPIView):
    override_serializer_classes = {
        'GET': ListSchemeAccountSerializer,
        'POST': CreateSchemeAccountSerializer,
        'OPTIONS': ListSchemeAccountSerializer,
    }

    def get_queryset(self):
        user = self.request.user
        return SchemeAccount.active_objects.filter(user=user)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            scheme_account = SchemeAccount.objects.create(
                user=request.user,
                scheme_id=data['scheme'],
                order=data['order'],
                status=SchemeAccount.WALLET_ONLY
            )
            SchemeAccountCredentialAnswer.objects.create(
                scheme_account=scheme_account,
                type=data['primary_answer_type'],
                answer=data['primary_answer'],
            )
        data['id'] = scheme_account.id
        return Response(data, status=status.HTTP_201_CREATED, content_type="application/json",
                        headers={'Location': reverse('retrieve_account', args=[scheme_account.id], request=request)})


class CreateAnswer(CreateAPIView):
    serializer_class = SchemeAccountAnswerSerializer


class RetrieveUpdateDestroyAnswer(RetrieveUpdateDestroyAPIView):
    serializer_class = SchemeAccountAnswerSerializer
    queryset = SchemeAccountCredentialAnswer.objects


class UpdateSchemeAccountStatus(GenericAPIView):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)
    serializer_class = StatusSerializer

    def post(self, request, *args, **kwargs):
        new_status_code = int(request.data['status'])
        if new_status_code not in [status_code[0] for status_code in SchemeAccount.STATUSES]:
            raise serializers.ValidationError('Invalid status code sent.')

        scheme_account = get_object_or_404(SchemeAccount, id=int(kwargs['pk']))
        if new_status_code != scheme_account.status:
            scheme_account.status = new_status_code
            scheme_account.save()

        return Response({
            'id': scheme_account.id,
            'status': new_status_code
        })


class Pagination(PageNumberPagination):
    page_size = 500


class ActiveSchemeAccountAccounts(ListAPIView):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)

    def get_queryset(self):
        return SchemeAccount.active_objects.filter(status=SchemeAccount.ACTIVE)

    serializer_class = SchemeAccountIdsSerializer
    pagination_class = Pagination


class SystemActionSchemeAccounts(ListAPIView):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)

    def get_queryset(self):
        return SchemeAccount.active_objects.filter(status__in=SchemeAccount.SYSTEM_ACTION_REQUIRED)

    serializer_class = SchemeAccountIdsSerializer
    pagination_class = Pagination


class SchemeAccountsCredentials(RetrieveAPIView):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)
    queryset = SchemeAccount.active_objects
    serializer_class = SchemeAccountCredentialsSerializer


def json_error_response(message, code):
    return Response({"message": message, "code": code}, status=code)

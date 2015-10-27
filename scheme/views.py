from rest_framework import generics
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView, RetrieveAPIView, \
    RetrieveUpdateDestroyAPIView, get_object_or_404, ListCreateAPIView, GenericAPIView
from rest_framework.pagination import PageNumberPagination
from scheme.models import Scheme, SchemeAccount
from scheme.serializers import (SchemeSerializer, SchemeAccountCredentialAnswer, SchemeAccountAnswerSerializer,
                                ListSchemeAccountSerializer, UpdateSchemeAccountSerializer,
                                CreateSchemeAccountSerializer, GetSchemeAccountSerializer, StatusSerializer,
                                ActiveSchemeAccountAccountsSerializer)
from rest_framework import status
from rest_framework.response import Response
from rest_framework import serializers
from user.authentication import ServiceAuthentication, AllowService


class SwappableSerializerMixin(object):
    serializer_class = None
    override_serializer_classes = None

    def get_serializer_class(self):
        return self.override_serializer_classes[self.request.method]


class SchemesList(generics.ListAPIView):
    queryset = Scheme.objects.filter(is_active=True)
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
            try:
                existing_primary_answer = scheme_account.primary_answer
            except SchemeAccountCredentialAnswer.DoesNotExist:
                # this shouldn't happen, but can if a scheme account is badly set up
                continue

            if request.data[primary_question.type] == existing_primary_answer.answer:
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
        if 'scheme' not in request.data:
            return json_error_response("Please specify a scheme", status.HTTP_400_BAD_REQUEST)

        scheme = get_object_or_404(Scheme, pk=request.data['scheme'])

        if scheme.primary_question.type not in request.data:
            return json_error_response("Does not include primary question ({}) response"
                                       .format(scheme.primary_question.type),
                                       status.HTTP_400_BAD_REQUEST)

        # Check that the user dosnt have a scheme account with the primary question answer
        scheme_accounts = SchemeAccount.active_objects.filter(scheme=scheme, user=request.user)
        primary_question = scheme.primary_question

        for scheme_account in scheme_accounts:
            try:
                existing_primary_answer = scheme_account.primary_answer
            except SchemeAccountCredentialAnswer.DoesNotExist:
                # this shouldn't happen, but can if a scheme account is badly set up
                continue

            if request.data[primary_question.type] == existing_primary_answer.answer:
                return json_error_response("A scheme account already exists with this {0}".format(
                    primary_question.label), status.HTTP_400_BAD_REQUEST)

        request.data['user'] = request.user.id
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scheme_account = serializer.save()

        headers = self.get_success_headers(serializer.data)
        response_data = {'id': scheme_account.id,
                         'scheme_id': scheme.id,
                         'order': scheme_account.order,
                         'status': scheme_account.status,
                         'points': None}

        for challenge in scheme.challenges:
            if challenge.type in request.data:
                response = request.data[challenge.type]
                obj, created = SchemeAccountCredentialAnswer.objects.update_or_create(
                    scheme_account=scheme_account, type=challenge.type, defaults={'answer': response})
                response_data[obj.type] = obj.answer

        points = scheme_account.get_midas_balance()
        scheme_account.save()
        response_data['points'] = points

        # Pop scheme and user because these are the only two keys not related to questions
        request.data.pop('scheme')
        request.data.pop('user')
        if list(request.data.keys()) == [scheme.primary_question.type]:
            scheme_account.status = SchemeAccount.WALLET_ONLY
            scheme_account.save()

        response_data['status'] = scheme_account.status

        return Response(response_data,
                        status=status.HTTP_201_CREATED,
                        headers=headers,
                        content_type="application/json")


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


class ActiveSchemeAccountAccounts(generics.ListAPIView):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)

    def get_queryset(self):
        return SchemeAccount.active_objects.filter(status=SchemeAccount.ACTIVE)

    serializer_class = ActiveSchemeAccountAccountsSerializer
    pagination_class = Pagination


class SystemActionSchemeAccountAccounts(generics.ListAPIView):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)

    def get_queryset(self):
        return SchemeAccount.active_objects.filter(status__in=SchemeAccount.SYSTEM_ACTION_REQUIRED)

    serializer_class = ActiveSchemeAccountAccountsSerializer
    pagination_class = Pagination


def json_error_response(message, code):
    return Response({"message": message, "code": code}, status=code)

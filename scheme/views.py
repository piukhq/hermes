import json
import requests
from rest_framework import generics
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView, RetrieveAPIView, \
    RetrieveUpdateDestroyAPIView, get_object_or_404, ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from hermes import settings
from scheme.encyption import AESCipher
from scheme.models import Scheme, SchemeAccount
from scheme.serializers import SchemeSerializer, SchemeAccountSerializer, SchemeAccountCredentialAnswer, \
    SchemeAccountAnswerSerializer, ListSchemeAccountSerializer, UpdateSchemeAccountSerializer
from rest_framework import status
from rest_framework.response import Response
from user.authenticators import UIDAuthentication


class SwappableSerializerMixin(object):
    def get_serializer_class(self):
        try:
            return self.override_serializer_classes[self.request.method]
        except KeyError:
            # required if you don't include all the methods (option, etc) in your serializer_class
            return super(SwappableSerializerMixin, self).get_serializer_class()


class SchemesList(generics.ListAPIView):
    queryset = Scheme.objects.filter(is_active=True)
    serializer_class = SchemeSerializer


class RetrieveScheme(RetrieveAPIView):
    queryset = Scheme.objects
    serializer_class = SchemeSerializer


class RetrieveUpdateDeleteAccount(SwappableSerializerMixin, RetrieveUpdateAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = SchemeAccountSerializer
    override_serializer_classes = {
        'PUT': UpdateSchemeAccountSerializer,
        'PATCH': UpdateSchemeAccountSerializer,
    }

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
        return Response(response_data)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status = SchemeAccount.DELETED
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreateAccount(SwappableSerializerMixin, ListCreateAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = SchemeAccountSerializer
    override_serializer_classes = {
        'GET': ListSchemeAccountSerializer
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

        # Make call to Midas
        serialized_credentials = None
        try:
            serialized_credentials = json.dumps(scheme_account.credentials())
        except SchemeAccountCredentialAnswer.DoesNotExist:
            scheme_account.status = 5
            scheme_account.save()

        if serialized_credentials:
            encrypted_credentials = AESCipher(settings.AES_KEY.encode()).encrypt(serialized_credentials).decode('utf-8')
            parameters = {'scheme_account_id': scheme_account.id, 'user_id': scheme_account.user.id,
                          'credentials': encrypted_credentials}
            try:
                response = requests.get('{}/{}/balance'.format(settings.MIDAS_URL, scheme.slug), params=parameters)
                if response.status_code == 200:
                    scheme_account.status = 1
                    response_data['points'] = response.json()['points']
                elif response.status_code == 403:
                    scheme_account.status = 2
                elif response.status_code == 432:
                    scheme_account.status = 2
                elif response.status_code == 429:
                    scheme_account.status_code = 7
                elif response.status_code == 434:
                    scheme_account.status = 6
                elif response.status_code == 530:
                    scheme_account.status = 3
                else:
                    scheme_account.status = 8
            except ConnectionError:
                scheme_account.status = 9
            scheme_account.save()

        response_data['status'] = scheme_account.status
        return Response(response_data,
                        status=status.HTTP_201_CREATED,
                        headers=headers,
                        content_type="application/json")


class CreateAnswer(CreateAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    serializer_class = SchemeAccountAnswerSerializer


class RetrieveUpdateDestroyAnswer(RetrieveUpdateDestroyAPIView):
    authentication_classes = (UIDAuthentication,)
    permission_classes = (IsAuthenticated,)

    serializer_class = SchemeAccountAnswerSerializer
    queryset = SchemeAccountCredentialAnswer.objects


def json_error_response(message, code):
    return Response({"message": message, "code": code}, status=code)

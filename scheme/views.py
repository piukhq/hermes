from rest_framework.generics import (RetrieveUpdateAPIView, RetrieveAPIView, ListAPIView, GenericAPIView,
                                     RetrieveUpdateDestroyAPIView, get_object_or_404, ListCreateAPIView,)
from rest_framework.pagination import PageNumberPagination
from scheme.models import Scheme, SchemeAccount, SchemeAccountCredentialAnswer
from scheme.serializers import (SchemeSerializer, LinkSchemeSerializer, ListSchemeAccountSerializer,
                                UpdateSchemeAccountSerializer, CreateSchemeAccountSerializer,
                                GetSchemeAccountSerializer, SchemeAccountCredentialsSerializer,
                                SchemeAccountIdsSerializer, StatusSerializer, ResponseLinkSerializer)
from rest_framework import status
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.reverse import reverse
from user.authentication import ServiceAuthentication, AllowService
from django.db import transaction


class SwappableSerializerMixin(object):
    serializer_class = None
    override_serializer_classes = None
    context = None

    def get_serializer_class(self):
        return self.override_serializer_classes[self.request.method]


class SchemesList(ListAPIView):
    """
    Retrieve a list of loyalty schemes.
    """
    queryset = Scheme.objects
    serializer_class = SchemeSerializer


class RetrieveScheme(RetrieveAPIView):
    """
    Retrieve a Loyalty Scheme.
    """
    queryset = Scheme.objects
    serializer_class = SchemeSerializer


class RetrieveUpdateDeleteAccount(SwappableSerializerMixin, RetrieveUpdateAPIView):
    """
    Get, update and delete scheme accounts.
    """
    override_serializer_classes = {
        'PUT': UpdateSchemeAccountSerializer,
        'PATCH': UpdateSchemeAccountSerializer,
        'GET': GetSchemeAccountSerializer,
        'DELETE': GetSchemeAccountSerializer,
        'OPTIONS': GetSchemeAccountSerializer,
    }

    queryset = SchemeAccount.active_objects

    def update(self, request, *args, **kwargs):
        """
        Update a users scheme account.<br>
        This will attempt to log into the loyalty scheme endsite and retrieve points.
        ---
        responseMessages:
            - code: 404
              message: Error retrieving the scheme account information.
            - code: 400
              message: A scheme account already exists with this primary question
        """
        scheme_account = get_object_or_404(SchemeAccount, user=request.user, id=kwargs['pk'])
        self.context = {'scheme': scheme_account.scheme}
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        scheme_account.order = data.get('order', scheme_account.order)
        answer = SchemeAccountCredentialAnswer.objects.get(scheme_account=scheme_account,
                                                           type=scheme_account.primary_answer.type)
        answer.answer = data.get('primary_answer', answer.answer)
        answer.save()

        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        """
        Marks a users scheme account as deleted.
        Responds with a 204 - No content.
        """
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LinkCredentials(GenericAPIView):
    serializer_class = LinkSchemeSerializer

    def post(self, request, *args, **kwargs):
        """
        Link credentials for loyalty scheme login
        ---
        response_serializer: ResponseLinkSerializer
        """
        serializer = LinkSchemeSerializer(data=request.data, context={'pk': self.kwargs['pk']})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        scheme_account = data.pop('scheme_account')
        for answer_type, answer in data.items():
            SchemeAccountCredentialAnswer.objects.update_or_create(
                type=answer_type, scheme_account=scheme_account, defaults={'answer': answer})
        response_data = {
            'balance': scheme_account.get_midas_balance(),
            'status': scheme_account.status,
            'status_name': scheme_account.status_name
        }
        out_serializer = ResponseLinkSerializer(response_data)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class CreateAccount(SwappableSerializerMixin, ListCreateAPIView):
    """
    Retrieve a scheme account using the scheme account id.
    """
    override_serializer_classes = {
        'GET': ListSchemeAccountSerializer,
        'POST': CreateSchemeAccountSerializer,
        'OPTIONS': ListSchemeAccountSerializer,
    }

    def get_queryset(self):
        user = self.request.user
        return SchemeAccount.active_objects.filter(user=user)

    def post(self, request, *args, **kwargs):
        """
        Create a new scheme account within the users wallet.<br>
        This does not log into the loyalty scheme end site.
        ---
        response_serializer: ResponseLinkSerializer
        """
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
        return Response(data, status=status.HTTP_201_CREATED,
                        headers={'Location': reverse('retrieve_account', args=[scheme_account.id], request=request)})


class UpdateSchemeAccountStatus(GenericAPIView):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)
    serializer_class = StatusSerializer

    def post(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS
        """
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
    """
    DO NOT USE - NOT FOR APP ACCESS
    """
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)

    def get_queryset(self):
        return SchemeAccount.active_objects.filter(status=SchemeAccount.ACTIVE)

    serializer_class = SchemeAccountIdsSerializer
    pagination_class = Pagination


class SystemActionSchemeAccounts(ListAPIView):
    """
    DO NOT USE - NOT FOR APP ACCESS
    """
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)

    def get_queryset(self):
        return SchemeAccount.active_objects.filter(status__in=SchemeAccount.SYSTEM_ACTION_REQUIRED)

    serializer_class = SchemeAccountIdsSerializer
    pagination_class = Pagination


class SchemeAccountsCredentials(RetrieveAPIView):
    """
    DO NOT USE - NOT FOR APP ACCESS
    """
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)
    queryset = SchemeAccount.active_objects
    serializer_class = SchemeAccountCredentialsSerializer


def json_error_response(message, code):
    return Response({"message": message, "code": code}, status=code)

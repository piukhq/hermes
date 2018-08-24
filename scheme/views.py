import analytics
import csv
import uuid
import requests
import socket
import json

from requests import RequestException
from raven.contrib.django.raven_compat.models import client as sentry
from collections import OrderedDict
from django.http import HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.utils import timezone
from rest_framework.generics import UpdateAPIView
from rest_framework.generics import (RetrieveAPIView, ListAPIView, GenericAPIView, get_object_or_404, ListCreateAPIView)
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from scheme.encyption import AESCipher
from scheme.my360endpoints import SCHEME_API_DICTIONARY
from scheme.forms import CSVUploadForm
from scheme.models import (Scheme, SchemeAccount, SchemeAccountCredentialAnswer, Exchange, SchemeImage,
                           SchemeAccountImage, UserConsent, JourneyTypes, ConsentStatus)

from scheme.serializers import (SchemeSerializer, LinkSchemeSerializer, ListSchemeAccountSerializer,
                                CreateSchemeAccountSerializer, GetSchemeAccountSerializer, UpdateCredentialSerializer,
                                SchemeAccountCredentialsSerializer, SchemeAccountIdsSerializer,
                                StatusSerializer, ResponseLinkSerializer, DeleteCredentialSerializer,
                                SchemeAccountSummarySerializer, ResponseSchemeAccountAndBalanceSerializer,
                                SchemeAnswerSerializer, DonorSchemeSerializer, ReferenceImageSerializer,
                                QuerySchemeAccountSerializer, JoinSerializer, UserConsentSerializer,
                                MidasUserConsentSerializer, UpdateUserConsentSerializer)
from rest_framework import status
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.reverse import reverse
from user.authentication import ServiceAuthentication, AllowService, JwtAuthentication
from django.db import transaction
from scheme.account_status_summary import scheme_account_status_data
from io import StringIO
from django.conf import settings
from user.models import CustomUser, UserSetting


class BaseLinkMixin(object):

    @staticmethod
    def link_account(serializer, scheme_account):
        serializer.is_valid(raise_exception=True)

        return BaseLinkMixin._link_account(serializer.validated_data, scheme_account)

    @staticmethod
    def _link_account(data, scheme_account):
        if 'consents' in data:
            consent_data = data.pop('consents')
        else:
            consent_data = []

        for answer_type, answer in data.items():
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(answer_type),
                scheme_account=scheme_account, defaults={'answer': answer})

        user_consents = UserConsentSerializer.get_user_consents(scheme_account, consent_data)
        UserConsentSerializer.validate_consents(user_consents, scheme_account.scheme.id, JourneyTypes.LINK.value)

        user_consent_serializer = MidasUserConsentSerializer(user_consents, many=True)

        midas_information = scheme_account.get_midas_balance(user_consents=user_consent_serializer.data)
        response_data = {
            'balance': midas_information
        }
        response_data['status'] = scheme_account.status
        response_data['status_name'] = scheme_account.status_name
        response_data.update(dict(data))

        if consent_data and scheme_account.status == SchemeAccount.ACTIVE:
            for user_consent in user_consents:
                user_consent.status = ConsentStatus.SUCCESS
                user_consent.save()


        analytics.update_scheme_account_attribute(scheme_account)

        return response_data


class SwappableSerializerMixin(object):
    serializer_class = None
    override_serializer_classes = None
    context = None

    def get_serializer_class(self):
        return self.override_serializer_classes[self.request.method]


class SchemeAccountQuery(APIView):

    authentication_classes = (ServiceAuthentication,)

    def get(self, request):
        try:
            queryset = SchemeAccount.objects.filter(**dict(request.query_params.items()))
        except Exception as e:
            response = {
                'exception_class': e.__class__.__name__,
                'exception_args': e.args
            }
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        serializer = QuerySchemeAccountSerializer(instance=queryset, many=True)
        return Response(serializer.data)


class SchemesList(ListAPIView):
    """
    Retrieve a list of loyalty schemes.
    """
    authentication_classes = (JwtAuthentication, ServiceAuthentication)
    queryset = Scheme.objects
    serializer_class = SchemeSerializer


class RetrieveScheme(RetrieveAPIView):
    """
    Retrieve a Loyalty Scheme.
    """
    queryset = Scheme.objects
    serializer_class = SchemeSerializer


class RetrieveDeleteAccount(SwappableSerializerMixin, RetrieveAPIView):
    """
    Get, update and delete scheme accounts.
    """
    override_serializer_classes = {
        'GET': GetSchemeAccountSerializer,
        'DELETE': GetSchemeAccountSerializer,
        'OPTIONS': GetSchemeAccountSerializer,
    }

    def get_queryset(self):
        return SchemeAccount.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        """
        Marks a users scheme account as deleted.
        Responds with a 204 - No content.
        """
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()

        analytics.update_scheme_account_attribute(instance)

        return Response(status=status.HTTP_204_NO_CONTENT)


class UpdateUserConsent(UpdateAPIView):
    authentication_classes = (ServiceAuthentication,)
    queryset = UserConsent.objects.all()
    serializer_class = UpdateUserConsentSerializer


class LinkCredentials(BaseLinkMixin, GenericAPIView):
    serializer_class = SchemeAnswerSerializer
    override_serializer_classes = {
        'PUT': SchemeAnswerSerializer,
        'POST': LinkSchemeSerializer,
        'OPTIONS': LinkSchemeSerializer,
        'DELETE': DeleteCredentialSerializer,
    }

    def put(self, request, *args, **kwargs):
        """Update manual answer or other credentials
        ---
        response_serializer: ResponseSchemeAccountAndBalanceSerializer
        """
        scheme_account = get_object_or_404(SchemeAccount.objects, id=self.kwargs['pk'], user=self.request.user)
        serializer = SchemeAnswerSerializer(data=request.data)
        response_data = self.link_account(serializer, scheme_account)
        out_serializer = ResponseSchemeAccountAndBalanceSerializer(response_data)
        return Response(out_serializer.data)

    def post(self, request, *args, **kwargs):
        """
        Link credentials for loyalty scheme login
        ---
        response_serializer: ResponseLinkSerializer
        """
        scheme_account = get_object_or_404(SchemeAccount.objects, id=self.kwargs['pk'], user=self.request.user)
        serializer = LinkSchemeSerializer(data=request.data, context={'scheme_account': scheme_account,
                                                                      'user': request.user})

        serializer.is_valid(raise_exception=True)

        response_data = self.link_account(serializer, scheme_account)
        scheme_account.link_date = timezone.now()
        scheme_account.save()

        out_serializer = ResponseLinkSerializer(response_data)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class CreateAccount(SwappableSerializerMixin, ListCreateAPIView):
    override_serializer_classes = {
        'GET': ListSchemeAccountSerializer,
        'POST': CreateSchemeAccountSerializer,
        'OPTIONS': ListSchemeAccountSerializer,
    }

    def get(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS
        """
        return super().get(self, request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        return SchemeAccount.objects.filter(user=user)

    def post(self, request, *args, **kwargs):
        """
        Create a new scheme account within the users wallet.<br>
        This does not log into the loyalty scheme end site.
        """
        return self.create_account(request, *args, **kwargs)

    def create_account(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # my360 schemes should never come through this endpoint
        scheme = Scheme.objects.get(id=data['scheme'])
        if scheme.url == settings.MY360_SCHEME_URL:

            metadata = {
                'scheme name': scheme.name,
            }
            analytics.post_event(
                request.user,
                analytics.events.MY360_APP_EVENT,
                metadata,
                True
            )

            raise serializers.ValidationError({
                "non_field_errors": [
                    "Invalid Scheme: {}. Please use /schemes/accounts/my360 endpoint".format(scheme.slug)
                ]
            })

        self._create_account(request.user, data, serializer.context['answer_type'])
        return Response(
            data,
            status=status.HTTP_201_CREATED,
            headers={'Location': reverse('retrieve_account', args=[data['id']], request=request)}
        )

    def _create_account(self, user, data, answer_type):
        if type(data) == int:
            return(data)
        with transaction.atomic():
            try:
                scheme_account = SchemeAccount.objects.get(
                    user=user,
                    scheme_id=data['scheme'],
                    status=SchemeAccount.JOIN
                )

                scheme_account.order = data['order']
                scheme_account.status = SchemeAccount.WALLET_ONLY
                scheme_account.save()
            except SchemeAccount.DoesNotExist:
                scheme_account = SchemeAccount.objects.create(
                    user=user,
                    scheme_id=data['scheme'],
                    order=data['order'],
                    status=SchemeAccount.WALLET_ONLY
                )
            SchemeAccountCredentialAnswer.objects.create(
                scheme_account=scheme_account,
                question=scheme_account.question(answer_type),
                answer=data[answer_type],
            )
        data['id'] = scheme_account.id

        user_consents = []
        if 'consents' in data:
            user_consents = UserConsentSerializer.get_user_consents(scheme_account, data.pop('consents'))
        UserConsentSerializer.validate_consents(user_consents, scheme_account.scheme, JourneyTypes.ADD.value)
        for user_consent in user_consents:
            user_consent.status = ConsentStatus.SUCCESS
            user_consent.save()

        analytics.update_scheme_account_attribute(scheme_account)

        return scheme_account


class CreateMy360AccountsAndLink(BaseLinkMixin, CreateAccount):
    """
        Create a new scheme account within the users wallet.
        Then link credentials for loyalty scheme login.
        Generic My360 scheme will create and link all paired
        My360 schemes.
    """
    override_serializer_classes = {
        'POST': CreateSchemeAccountSerializer,
    }

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request_data = self.get_required_my360_data(serializer.validated_data)

        if request_data['error_response']:
            return request_data['error_response']

        # if passing generic My360 scheme slug, create and link all paired scheme accounts
        elif request_data['scheme_obj'].slug == 'my360':
            return self.create_and_link_schemes(request_data, request.user)

        # else create and link the one requested My360 scheme account
        else:
            return self.create_and_link_scheme(request_data, request.user)

    def get_required_my360_data(self, request_data):
        credential_type = 'barcode'
        credential_value = request_data.get(credential_type)
        scheme_id = request_data.get('scheme')
        scheme_obj = Scheme.objects.get(id=int(scheme_id))
        try:
            scheme_slugs = self.get_my360_schemes(credential_value) if scheme_obj.slug == 'my360' else None
            error = None
        except Exception:
            scheme_slugs = []
            error = Response(
                        {'code': 400, 'message': 'Error getting schemes from My360'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        if 'consents' in request_data:
            consent_data = request_data.pop('consents')
        else:
            consent_data = []

        my360_info = {
            'credential_type': credential_type,
            'scheme_obj': scheme_obj,
            'scheme_slugs': scheme_slugs,
            'error_response': error,
            'new_scheme_data': {
                'barcode': credential_value,
                'order': request_data.get('order'),
                'scheme': scheme_id if not scheme_obj.slug == 'my360' else None,
                'consents': consent_data
            }
        }

        return my360_info

    @staticmethod
    def get_my360_schemes(barcode):

        def convert_scheme_code_list_to_scheme_slugs(scheme_code_list):
            schemes = []
            for scheme_code in scheme_code_list:
                scheme_slug = SCHEME_API_DICTIONARY.get(scheme_code)
                if scheme_slug:
                    schemes.append(scheme_slug)
            return schemes

        schemes_url = settings.MY360_SCHEME_API_URL
        response = requests.get(schemes_url.format(barcode))
        if response.status_code == 200:
            valid = response.json().get('valid')
            if valid:
                scheme_code_list = response.json().get('schemes')
                scheme_slugs = convert_scheme_code_list_to_scheme_slugs(scheme_code_list)

                return scheme_slugs

        raise ValueError('Invalid response from My360 while getting a cards scheme list')

    def create_and_link_schemes(self, request_data, user):
        scheme_accounts_response = []
        new_scheme_data = request_data['new_scheme_data']
        for scheme in request_data['scheme_slugs']:
            try:
                scheme_id = Scheme.objects.get(slug=scheme).id

            except Exception:
                sentry.captureException()
                continue

            if not SchemeAccount.objects.filter(scheme_id=scheme_id, user=user):
                new_scheme_data['scheme'] = scheme_id
                scheme_account = self._create_account(user, new_scheme_data.copy(), request_data['credential_type'])
                link_response = self._link_scheme_account(request_data['credential_type'],
                                                          new_scheme_data.copy(), scheme_account)
                if link_response:
                    scheme_accounts_response.append(link_response)

        if scheme_accounts_response:
            return Response(scheme_accounts_response, status=status.HTTP_201_CREATED)

        if request_data['scheme_slugs']:
            return Response({'Error': 'Error linking My360 card, not adding scheme account'},
                            status=status.HTTP_400_BAD_REQUEST
                            )

        return Response({'Error': 'No paired schemes found for this card'},
                        status=status.HTTP_400_BAD_REQUEST,
                        )

    def create_and_link_scheme(self, request_data, user):
        scheme_account = self._create_account(user,
                                              request_data['new_scheme_data'].copy(), request_data['credential_type'])
        link_response = self._link_scheme_account(request_data['credential_type'],
                                                  request_data['new_scheme_data'].copy(), scheme_account)

        if link_response:
            return Response([link_response], status=status.HTTP_201_CREATED)

        return Response({'Error': 'Error linking My360 card, not adding scheme account'},
                        status=status.HTTP_400_BAD_REQUEST
                        )

    def _link_scheme_account(self, credential_type, data, scheme_account):
        response_data = self._link_account(OrderedDict({credential_type: data[credential_type],
                                                        'consents': data['consents']}), scheme_account)
        if response_data['balance']:
            scheme_account.link_date = timezone.now()
            scheme_account.save()

            return self._format_response(credential_type, scheme_account, response_data)

        try:
            scheme_account.delete()
            return None
        except Exception:
            sentry.captureException()

    @staticmethod
    def _format_response(credential_type, scheme_account, linked_data):
        linked_data = ResponseLinkSerializer(linked_data)
        response = {
            'order': scheme_account.order,
            'barcode': scheme_account.barcode,
            'scheme': scheme_account.scheme.id,
            'id': scheme_account.id,
        }
        response.update(linked_data.data)

        return response


class CreateJoinSchemeAccount(APIView):
    authentication_classes = (ServiceAuthentication,)

    def post(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS
        ---
        response_serializer: GetSchemeAccountSerializer
        """
        try:
            scheme = Scheme.objects.get(slug=kwargs['scheme_slug'])
        except Scheme.DoesNotExist:
            return Response({'code': 400, 'message': 'Scheme does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(id=kwargs['user_id'])
        except CustomUser.DoesNotExist:
            return Response({'code': 400, 'message': 'User does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

        # has the user disabled join cards for this scheme?
        setting = UserSetting.objects.filter(user=user, setting__scheme=scheme,
                                             setting__slug='join-{}'.format(scheme.slug))
        if setting.exists() and setting.first().value == '0':
            return Response({'code': 200, 'message': 'User has disabled join cards for this scheme'},
                            status=status.HTTP_200_OK)

        # does the user have an account with the scheme already?
        account = SchemeAccount.objects.filter(scheme=scheme, user=user)
        if account.exists():
            return Response({'code': 200, 'message': 'User already has an account with this scheme.'},
                            status=status.HTTP_200_OK)

        # create a join account.
        account = SchemeAccount(
            user=user,
            scheme=scheme,
            status=SchemeAccount.JOIN,
            order=0,
        )
        account.save()

        metadata = {
            'company name': scheme.company,
            'slug': scheme.slug
        }
        analytics.post_event(
            user,
            analytics.events.ISSUED_JOIN_CARD_EVENT,
            metadata,
            True
        )
        analytics.update_scheme_account_attribute(account)

        # serialize the account for the response.
        serializer = GetSchemeAccountSerializer(instance=account)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


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
        return SchemeAccount.objects.filter(status=SchemeAccount.ACTIVE)

    serializer_class = SchemeAccountIdsSerializer
    pagination_class = Pagination


class SystemActionSchemeAccounts(ListAPIView):
    """
    DO NOT USE - NOT FOR APP ACCESS
    """
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)

    def get_queryset(self):
        return SchemeAccount.objects.filter(status__in=SchemeAccount.SYSTEM_ACTION_REQUIRED)

    serializer_class = SchemeAccountIdsSerializer
    pagination_class = Pagination


class SchemeAccountsCredentials(RetrieveAPIView):
    """
    DO NOT USE - NOT FOR APP ACCESS
    """
    authentication_classes = (JwtAuthentication, ServiceAuthentication)
    serializer_class = SchemeAccountCredentialsSerializer

    def get_queryset(self):
        queryset = SchemeAccount.objects
        if self.request.user.uid != 'api_user':
            queryset = queryset.filter(user=self.request.user)
        return queryset

    def put(self, request, *args, **kwargs):
        """
        Update / Create credentials for loyalty scheme login
        ---
        """
        scheme_account = get_object_or_404(SchemeAccount.objects, id=self.kwargs['pk'])
        serializer = UpdateCredentialSerializer(data=request.data, context={'scheme_account': scheme_account})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'consents' in data:
            data.pop('consents')
        updated_credentials = []

        for credential_type in data.keys():
            question = scheme_account.scheme.questions.get(type=credential_type)
            SchemeAccountCredentialAnswer.objects.update_or_create(question=question, scheme_account=scheme_account,
                                                                   defaults={'answer': data[credential_type]})
            updated_credentials.append(credential_type)

        return Response({'updated': updated_credentials}, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        """
        Delete scheme credential answers from a scheme account
        ---
        parameters:
          - name: all
            required: false
            description: boolean, True will delete all scheme credential answers
           - name: property_list
            required: false
            description: list, e.g. ['link_questions'] takes properties from the scheme
          - name: type_list
            required: false
            description: list, e.g. ['username', 'password'] of all credential types to delete
        """
        scheme_account = get_object_or_404(SchemeAccount.objects, id=self.kwargs['pk'])
        serializer = DeleteCredentialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        answers_to_delete = self.collect_credentials_to_delete(scheme_account, data)
        if type(answers_to_delete) is Response:
            return answers_to_delete

        response_list = [answer.question.type for answer in answers_to_delete]
        response_list.sort()
        for answer in answers_to_delete:
            answer.delete()

        if not response_list:
            return Response({'message': 'No answers found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'deleted': str(response_list)}, status=status.HTTP_200_OK)

    def collect_credentials_to_delete(self, scheme_account, request_data):
        credential_list = scheme_account.schemeaccountcredentialanswer_set.all()
        answers_to_delete = set()

        if request_data.get('all'):
            answers_to_delete.update(credential_list)
            return answers_to_delete

        for credential_property in request_data.get('property_list'):
            try:
                questions = getattr(scheme_account.scheme, credential_property)
                answers_to_delete.update(self.get_answers_from_question_list(scheme_account, questions))
            except AttributeError:
                return self.invalid_data_response(credential_property)

        scheme_account_types = [answer.question.type for answer in credential_list]
        question_list = []
        for answer_type in request_data.get('type_list'):
            if answer_type in scheme_account_types:
                question_list.append(scheme_account.scheme.questions.get(type=answer_type))
            else:
                return self.invalid_data_response(answer_type)

        answers_to_delete.update(self.get_answers_from_question_list(scheme_account, question_list))

        return answers_to_delete

    @staticmethod
    def get_answers_from_question_list(scheme_account, questions):
        answers = []
        for question in questions:
            credential_answer = scheme_account.schemeaccountcredentialanswer_set.get(question=question)
            if credential_answer:
                answers.append(credential_answer)

        return answers

    @staticmethod
    def invalid_data_response(invalid_data):
        message = {'message': 'No answers found for: {}. Not deleting any credential answers'.format(invalid_data)}
        return Response(message, status=status.HTTP_404_NOT_FOUND)


class SchemeAccountStatusData(ListAPIView):
    """
    DO NOT USE - NOT FOR APP ACCESS
    """
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)

    def get_queryset(self):
        queryset = scheme_account_status_data()

        return queryset

    serializer_class = SchemeAccountSummarySerializer


# TODO: Make this a class based view
# TODO: Better handling of incorrect emails
def csv_upload(request):
    # If we had a POST then get the request post values.
    form = CSVUploadForm()
    if request.method == 'POST':

        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            scheme = Scheme.objects.get(id=int(request.POST['scheme']))
            uploaded_file = StringIO(request.FILES['emails'].file.read().decode())
            image_criteria_instance = SchemeAccountImage(scheme=scheme, start_date=timezone.now())
            image_criteria_instance.save()
            csvreader = csv.reader(uploaded_file, delimiter=',', quotechar='"')
            for row in csvreader:
                for email in row:
                    scheme_account = SchemeAccount.objects.filter(user__email=email.lstrip(), scheme=scheme)
                    if scheme_account:
                        image_criteria_instance.scheme_accounts.add(scheme_account.first())
                    else:
                        image_criteria_instance.delete()
                        return HttpResponseBadRequest()

            return redirect('/admin/scheme/schemeaccountimage/{}'.format(image_criteria_instance.id))

    context = {'form': form}
    return render(request, 'admin/csv_upload_form.html', context)


class DonorSchemes(APIView):

    authentication_classes = (ServiceAuthentication,)

    def get(self, request, *args, **kwargs):
        """
        DO NOT USE - SERVICE NOT FOR PUBLIC ACCESS
        ---
        response_serializer: scheme.serializers.DonorSchemeAccountSerializer

        """
        host_scheme = Scheme.objects.filter(pk=kwargs['scheme_id'])
        scheme_accounts = SchemeAccount.objects.filter(user__id=kwargs['user_id'], status=SchemeAccount.ACTIVE)
        exchanges = Exchange.objects.filter(host_scheme=host_scheme, donor_scheme__in=scheme_accounts.values('scheme'))
        return_data = []

        for e in exchanges:
            scheme_account = scheme_accounts.get(scheme=e.donor_scheme)
            data = DonorSchemeSerializer(e).data
            data['scheme_account_id'] = scheme_account.id
            return_data.append(data)

        return Response(return_data, status=200)


class ReferenceImages(APIView):
    authentication_classes = (ServiceAuthentication,)

    override_serializer_classes = {
        'GET': ReferenceImageSerializer,
    }

    def get(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS
        ---
        response_serializer: ReferenceImageSerializer
        """
        # TODO: refactor image types to allow SchemeImage.REFERENCE instead of magic number 5.
        images = SchemeImage.objects.filter(image_type_code=5)
        reference_image_serializer = ReferenceImageSerializer(images, many=True)

        return_data = [{
            'file': data["image"],
            'scheme_id': data["scheme"]
        } for data in reference_image_serializer.data]

        return Response(return_data, status=200)


class IdentifyCard(APIView):
    authentication_classes = (JwtAuthentication,)

    def post(self, request, *args, **kwargs):
        """
        Identifies and associates a given card image with a scheme ID.
        ---
        parameters:
          - name: base64img
            required: true
            description: the base64 encoded image to identify
        response_serializer: scheme.serializers.IdentifyCardSerializer
        responseMessages:
          - code: 400
            message: no match
        """
        data = {
            'uuid': str(uuid.uuid4()),
            'base64img': request.data['base64img']
        }
        headers = {
            'Content-Type': 'application/json'
        }
        resp = requests.post(settings.HECATE_URL + '/classify', json=data, headers=headers)
        json = resp.json()

        if json['status'] != 'success' or json['reason'] == 'no match':
            return Response({'status': 'failure', 'message': json['reason']},
                            status=400)

        return Response({
            'scheme_id': int(json['scheme_id'])
        }, status=200)


class Join(SwappableSerializerMixin, GenericAPIView):
    override_serializer_classes = {
        'POST': JoinSerializer,
    }

    def post(self, request, *args, **kwargs):
        """
        Create a new scheme account,
        Register a new loyalty account on the requested scheme,
        Link the newly created loyalty account with the created scheme account.
        """

        scheme_id = int(self.kwargs['pk'])
        join_scheme = get_object_or_404(Scheme.objects, id=scheme_id)
        serializer = JoinSerializer(data=request.data, context={
                                                                'scheme': join_scheme,
                                                                'user': request.user
                                                                })
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data['scheme'] = scheme_id

        scheme_account = self.create_join_account(data, request.user, scheme_id)

        try:
            if 'consents' in serializer.validated_data:
                consent_data = serializer.validated_data.pop('consents')
            else:
                consent_data = []

            user_consents = UserConsentSerializer.get_user_consents(scheme_account, consent_data)

            UserConsentSerializer.validate_consents(user_consents, scheme_id, JourneyTypes.JOIN.value)

            # Deserialize the user consent instances formatted to send to Midas
            user_consent_serializer = MidasUserConsentSerializer(user_consents, many=True)
            for user_consent in user_consents:
                user_consent.save()

                data['credentials'].update(consents=user_consent_serializer.data)

            data['id'] = scheme_account.id
            if data['save_user_information']:
                self.save_user_profile(data['credentials'], request.user)

            self.post_midas_join(scheme_account, data['credentials'], join_scheme.slug)

            keys_to_remove = ['save_user_information', 'credentials']
            response_dict = {key: value for (key, value) in data.items() if key not in keys_to_remove}

            return Response(
                response_dict,
                status=status.HTTP_201_CREATED,
            )
        except serializers.ValidationError:
            self.handle_failed_join(scheme_account)
            raise
        except Exception as e:
            self.handle_failed_join(scheme_account)

            return Response(
                {'message': 'Unknown error with join'},
                status=status.HTTP_200_OK,
            )

    @staticmethod
    def handle_failed_join(scheme_account):
        scheme_account_answers = scheme_account.schemeaccountcredentialanswer_set.all()
        [answer.delete() for answer in scheme_account_answers]

        scheme_account.status = SchemeAccount.JOIN
        scheme_account.save()
        sentry.captureException()

    @staticmethod
    def create_join_account(data, user, scheme_id):
        with transaction.atomic():
            try:
                scheme_account = SchemeAccount.objects.get(
                    user=user,
                    scheme_id=scheme_id,
                    status=SchemeAccount.JOIN
                )

                scheme_account.order = data['order']
                scheme_account.status = SchemeAccount.PENDING
                scheme_account.save()
            except SchemeAccount.DoesNotExist:
                scheme_account = SchemeAccount.objects.create(
                    user=user,
                    scheme_id=data['scheme'],
                    order=data['order'],
                    status=SchemeAccount.PENDING
                )

        analytics.update_scheme_account_attribute(scheme_account)

        return scheme_account

    @staticmethod
    def save_user_profile(credentials, user):
        for question, answer in credentials.items():
            try:
                user.profile.set_field(question, answer)
            except AttributeError:
                continue
        user.profile.save()

    @staticmethod
    def post_midas_join(scheme_account, credentials_dict, slug):
        for question in scheme_account.scheme.link_questions:
            question_type = question.type
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(question_type),
                scheme_account=scheme_account,
                answer=credentials_dict[question_type])

        encrypted_credentials = AESCipher(
            settings.AES_KEY.encode()).encrypt(json.dumps(credentials_dict)).decode('utf-8')

        data = {
            'scheme_account_id': scheme_account.id,
            'credentials': encrypted_credentials,
            'user_id': scheme_account.user.id,
            'status': scheme_account.status,
            'journey_type': JourneyTypes.JOIN.value
        }
        headers = {"transaction": str(uuid.uuid1()), "User-agent": 'Hermes on {0}'.format(socket.gethostname())}
        response = requests.post('{}/{}/register'.format(settings.MIDAS_URL, slug),
                                 json=data, headers=headers)

        message = response.json().get('message')
        if not message == "success":
            raise RequestException(
                'Error creating join task in Midas. Response message :{}'.format(message)
            )

import csv
import json
import socket
import uuid
from io import StringIO

import requests
from django.conf import settings
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.utils import timezone
from raven.contrib.django.raven_compat.models import client as sentry
from requests import RequestException
from rest_framework import serializers, status
from rest_framework.generics import (GenericAPIView, ListAPIView, ListCreateAPIView, RetrieveAPIView, get_object_or_404)
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from intercom import intercom_api
from scheme.account_status_summary import scheme_account_status_data
from scheme.encyption import AESCipher
from scheme.forms import CSVUploadForm
from scheme.models import (Exchange, Scheme, SchemeAccount, SchemeAccountCredentialAnswer, SchemeAccountImage,
                           SchemeImage)
from scheme.serializers import (CreateSchemeAccountSerializer, DeleteCredentialSerializer, DonorSchemeSerializer,
                                GetSchemeAccountSerializer, JoinSerializer, LinkSchemeSerializer,
                                ListSchemeAccountSerializer, QuerySchemeAccountSerializer, ReferenceImageSerializer,
                                ResponseLinkSerializer, ResponseSchemeAccountAndBalanceSerializer,
                                SchemeAccountCredentialsSerializer, SchemeAccountIdsSerializer,
                                SchemeAccountSummarySerializer, SchemeAnswerSerializer, SchemeSerializer,
                                StatusSerializer, UpdateCredentialSerializer)
from ubiquity.models import PaymentCardAccountEntry, SchemeAccountEntry
from user.authentication import AllowService, JwtAuthentication, ServiceAuthentication
from user.models import CustomUser, UserSetting


class BaseLinkMixin(object):

    @staticmethod
    def link_account(serializer, scheme_account, user):
        serializer.is_valid(raise_exception=True)
        return BaseLinkMixin._link_account(serializer.validated_data, scheme_account, user)

    @staticmethod
    def _link_account(data, scheme_account, user):
        for answer_type, answer in data.items():
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(answer_type),
                scheme_account=scheme_account, defaults={'answer': answer})
        midas_information = scheme_account.get_cached_balance()
        response_data = {
            'balance': {**midas_information},
            'status': scheme_account.status,
            'status_name': scheme_account.status_name
        }
        response_data.update(dict(data))
        try:
            intercom_api.update_account_status_custom_attribute(settings.INTERCOM_TOKEN, scheme_account, user)
        except intercom_api.IntercomException:
            pass
        return response_data


class SwappableSerializerMixin(object):
    serializer_class = None
    override_serializer_classes = None
    context = None

    def get_serializer_class(self):
        return self.override_serializer_classes[self.request.method]


class IdentifyCardMixin:
    @staticmethod
    def _get_scheme(base_64_image):
        data = {
            'uuid': str(uuid.uuid4()),
            'base64img': base_64_image
        }
        headers = {
            'Content-Type': 'application/json'
        }
        resp = requests.post(settings.HECATE_URL + '/classify', json=data, headers=headers)
        return resp.json()


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
        return SchemeAccount.objects.filter(user_set__id=self.request.user.id)

    def delete(self, request, *args, **kwargs):
        """
        Marks a users scheme account as deleted.
        Responds with a 204 - No content.
        """
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        try:
            intercom_api.update_account_status_custom_attribute(settings.INTERCOM_TOKEN, instance, request.user)
        except intercom_api.IntercomException:
            pass

        return Response(status=status.HTTP_204_NO_CONTENT)


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
        scheme_account = get_object_or_404(SchemeAccount.objects, id=self.kwargs['pk'],
                                           user_set__id=self.request.user.id)
        serializer = SchemeAnswerSerializer(data=request.data)
        response_data = self.link_account(serializer, scheme_account, request.user)
        out_serializer = ResponseSchemeAccountAndBalanceSerializer(response_data)
        return Response(out_serializer.data)

    def post(self, request, *args, **kwargs):
        """
        Link credentials for loyalty scheme login
        ---
        response_serializer: ResponseLinkSerializer
        """
        scheme_account = get_object_or_404(SchemeAccount.objects, id=self.kwargs['pk'],
                                           user_set__id=self.request.user.id)
        serializer = LinkSchemeSerializer(data=request.data, context={'scheme_account': scheme_account,
                                                                      'user': request.user})

        serializer.is_valid(raise_exception=True)
        serializer.save()  # Save consents

        response_data = self.link_account(serializer, scheme_account, request.user)
        scheme_account.link_date = timezone.now()
        scheme_account.save()

        out_serializer = ResponseLinkSerializer(response_data)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class SchemeAccountCreationMixin(SwappableSerializerMixin):
    def create_account(self, data, user):
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # my360 schemes should never come through this endpoint
        scheme = Scheme.objects.get(id=data['scheme'])
        if scheme.url == settings.MY360_SCHEME_URL:
            try:
                metadata = {
                    'scheme name': scheme.name,
                }
                intercom_api.post_intercom_event(
                    settings.INTERCOM_TOKEN,
                    user.uid,
                    intercom_api.MY360_APP_EVENT,
                    metadata
                )

            except intercom_api.IntercomException:
                pass

            raise serializers.ValidationError({
                "non_field_errors": [
                    "Invalid Scheme: {}. Please use /schemes/accounts/my360 endpoint".format(scheme.slug)
                ]
            })
        answer_type = serializer.context['answer_type']
        try:
            query = {
                'scheme_account__scheme__id': data['scheme'],
                'answer': data[answer_type]
            }
            scheme_account = SchemeAccountCredentialAnswer.objects.get(**query).scheme_account
            data['id'] = scheme_account.id

            if scheme_account.is_deleted:
                scheme_account.is_deleted = False
                scheme_account.save()

            SchemeAccountEntry.objects.get_or_create(user=user, scheme_account=scheme_account)
            for card in scheme_account.payment_card_account_set.all():
                PaymentCardAccountEntry.objects.get_or_create(user=user, payment_card_account=card)

        except SchemeAccountCredentialAnswer.DoesNotExist:
            self._create_account(user, data, answer_type)

        return data

    @staticmethod
    def _create_account(user, data, answer_type):
        if type(data) == int:
            return data

        with transaction.atomic():
            try:
                scheme_account = SchemeAccount.objects.get(
                    user_set__id=user.id,
                    scheme_id=data['scheme'],
                    status=SchemeAccount.JOIN
                )

                scheme_account.order = data['order']
                scheme_account.status = SchemeAccount.WALLET_ONLY
                scheme_account.save()
            except SchemeAccount.DoesNotExist:
                scheme_account = SchemeAccount.objects.create(
                    scheme_id=data['scheme'],
                    order=data['order'],
                    status=SchemeAccount.WALLET_ONLY
                )
                SchemeAccountEntry.objects.create(scheme_account=scheme_account, user=user)

            SchemeAccountCredentialAnswer.objects.create(
                scheme_account=scheme_account,
                question=scheme_account.question(answer_type),
                answer=data[answer_type],
            )

        data['id'] = scheme_account.id
        try:
            intercom_api.update_account_status_custom_attribute(settings.INTERCOM_TOKEN, scheme_account, user)
        except intercom_api.IntercomException:
            pass

        return scheme_account


class CreateAccount(SchemeAccountCreationMixin, ListCreateAPIView):
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
        user_id = self.request.user.id
        return SchemeAccount.objects.filter(user_set__id=user_id)

    def post(self, request, *args, **kwargs):
        """
        Create a new scheme account within the users wallet.<br>
        This does not log into the loyalty scheme end site.
        """
        response = self.create_account(request.data, request.user)
        return Response(
            response,
            status=status.HTTP_201_CREATED,
            headers={'Location': reverse('retrieve_account', args=[response['id']], request=request)}
        )


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
        account = SchemeAccount.objects.filter(scheme=scheme, user_set__id=user.id)
        if account.exists():
            return Response({'code': 200, 'message': 'User already has an account with this scheme.'},
                            status=status.HTTP_200_OK)

        # create a join account.
        account = SchemeAccount(
            scheme=scheme,
            status=SchemeAccount.JOIN,
            order=0,
        )
        account.save()
        SchemeAccountEntry.objects.create(scheme_account=account, user=user)

        try:
            metadata = {
                'company name': scheme.company,
                'slug': scheme.slug
            }
            intercom_api.post_intercom_event(
                settings.INTERCOM_TOKEN,
                user.uid,
                intercom_api.ISSUED_JOIN_CARD_EVENT,
                metadata
            )
            intercom_api.update_account_status_custom_attribute(settings.INTERCOM_TOKEN, account, user)
        except intercom_api.IntercomException:
            pass

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
            queryset = queryset.filter(user_set__id=self.request.user.id)
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

    @staticmethod
    def get(request, *args, **kwargs):
        """
        DO NOT USE - SERVICE NOT FOR PUBLIC ACCESS
        ---
        response_serializer: scheme.serializers.DonorSchemeAccountSerializer

        """
        host_scheme = Scheme.objects.filter(pk=kwargs['scheme_id'])
        scheme_accounts = SchemeAccount.objects.filter(user_set__id=kwargs['user_id'], status=SchemeAccount.ACTIVE)
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


class IdentifyCard(APIView, IdentifyCardMixin):
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
        json = self._get_scheme(request.data['base64img'])

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
        serializer.save()  # Save consents
        data = serializer.validated_data
        data['scheme'] = scheme_id
        scheme_account = self.create_join_account(data, request.user, scheme_id)
        try:
            data['id'] = scheme_account.id
            if data['save_user_information']:
                self.save_user_profile(data['credentials'], request.user)

            self.post_midas_join(scheme_account, data['credentials'], join_scheme.slug, request.user.id)

            keys_to_remove = ['save_user_information', 'credentials']
            response_dict = {key: value for (key, value) in data.items() if key not in keys_to_remove}

            return Response(
                response_dict,
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            scheme_account_answers = scheme_account.schemeaccountcredentialanswer_set.all()
            [answer.delete() for answer in scheme_account_answers]
            scheme_account.status = SchemeAccount.JOIN
            scheme_account.save()
            sentry.captureException()

            return Response(
                {'message': 'Error with join'},
                status=status.HTTP_200_OK,
            )

    @staticmethod
    def create_join_account(data, user, scheme_id):
        with transaction.atomic():
            try:
                scheme_account = SchemeAccount.objects.get(
                    user_set__id=user.id,
                    scheme_id=scheme_id,
                    status=SchemeAccount.JOIN
                )

                scheme_account.order = data['order']
                scheme_account.status = SchemeAccount.PENDING
                scheme_account.save()
            except SchemeAccount.DoesNotExist:
                scheme_account = SchemeAccount.objects.create(
                    scheme_id=data['scheme'],
                    order=data['order'],
                    status=SchemeAccount.PENDING
                )
                SchemeAccountEntry.objects.create(scheme_account=scheme_account, user=user)

        try:
            intercom_api.update_account_status_custom_attribute(settings.INTERCOM_TOKEN, scheme_account, user)
        except intercom_api.IntercomException:
            pass

        return scheme_account

    @staticmethod
    def save_user_profile(credentials, user):
        for question, answer in credentials.items():
            try:
                setattr(user.profile, question, answer)
            except Exception:
                continue
        user.profile.save()

    @staticmethod
    def post_midas_join(scheme_account, credentials_dict, slug, user_id):
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
            'user_id': user_id
        }
        headers = {"transaction": str(uuid.uuid1()), "User-agent": 'Hermes on {0}'.format(socket.gethostname())}
        response = requests.post('{}/{}/register'.format(settings.MIDAS_URL, slug),
                                 json=data, headers=headers)

        message = response.json().get('message')
        if not message == "success":
            raise RequestException(
                'Error creating join task in Midas. Response message :{}'.format(message)
            )

import csv
import json
import logging
from io import StringIO
from typing import TYPE_CHECKING

import requests
import sentry_sdk
from django.conf import settings
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import (GenericAPIView, ListAPIView, ListCreateAPIView, RetrieveAPIView, UpdateAPIView,
                                     get_object_or_404)
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

import analytics
from payment_card.payment import Payment
from payment_card.models import PaymentCardAccount
from scheme.account_status_summary import scheme_account_status_data
from scheme.forms import CSVUploadForm
from scheme.mixins import (BaseLinkMixin, IdentifyCardMixin, SchemeAccountCreationMixin, SchemeAccountJoinMixin,
                           SwappableSerializerMixin, UpdateCredentialsMixin)
from scheme.models import (ConsentStatus, Exchange, Scheme, SchemeAccount, SchemeAccountImage, SchemeImage,
                           UserConsent, SchemeBundleAssociation)
from scheme.serializers import (CreateSchemeAccountSerializer, DeleteCredentialSerializer, DonorSchemeSerializer,
                                GetSchemeAccountSerializer, JoinSerializer, LinkSchemeSerializer,
                                ListSchemeAccountSerializer,
                                QuerySchemeAccountSerializer, ReferenceImageSerializer, ResponseLinkSerializer,
                                ResponseSchemeAccountAndBalanceSerializer, SchemeAccountCredentialsSerializer,
                                SchemeAccountIdsSerializer,
                                SchemeAccountSummarySerializer, SchemeAnswerSerializer, SchemeSerializer,
                                StatusSerializer, UpdateUserConsentSerializer)
from ubiquity.models import PaymentCardSchemeEntry, SchemeAccountEntry
from ubiquity.tasks import send_merchant_metrics_for_link_delete, async_join_journey_fetch_balance_and_update_status
from user.authentication import AllowService, JwtAuthentication, ServiceAuthentication
from user.models import CustomUser, UserSetting

if TYPE_CHECKING:
    from datetime import datetime


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
        serializer = QuerySchemeAccountSerializer(instance=queryset, many=True, context={'request': request})
        return Response(serializer.data)


class SchemesList(ListAPIView):
    """
    Retrieve a list of loyalty schemes.
    """
    authentication_classes = (JwtAuthentication, ServiceAuthentication)
    queryset = Scheme.objects
    serializer_class = SchemeSerializer

    def get_queryset(self):
        queryset = Scheme.objects
        query = {}

        if not self.request.user.is_tester:
            query['test_scheme'] = False

        return self.request.channels_permit.scheme_query(queryset.filter(**query))


class RetrieveScheme(RetrieveAPIView):
    """
    Retrieve a Loyalty Scheme.
    """
    queryset = Scheme.objects
    serializer_class = SchemeSerializer

    def get_queryset(self):
        queryset = Scheme.objects
        query = {}

        if not self.request.user.is_tester:
            query['test_scheme'] = False

        return self.request.channels_permit.scheme_query(queryset.filter(**query))


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
        queryset = SchemeAccount.objects
        query = {'user_set__id': self.request.user.id}

        if not self.request.user.is_tester:
            query['scheme__test_scheme'] = False

        return self.request.channels_permit.scheme_account_query(queryset.filter(**query))

    def delete(self, request, *args, **kwargs):
        """
        Marks a users scheme account as deleted.
        Responds with a 204 - No content.
        """
        instance = self.get_object()
        SchemeAccountEntry.objects.get(scheme_account=instance, user__id=request.user.id).delete()

        if instance.user_set.count() < 1:
            instance.is_deleted = True
            instance.save()

            if request.user.client_id == settings.BINK_CLIENT_ID:
                analytics.update_scheme_account_attribute(
                    instance,
                    request.user,
                    old_status=dict(instance.STATUSES).get(instance.status_key))

            PaymentCardSchemeEntry.objects.filter(scheme_account=instance).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class ServiceDeleteAccount(APIView):
    """
    Marks scheme account as deleted and remove all related scheme account entries.
    Responds with a 204 - No content.
    """
    authentication_classes = (ServiceAuthentication,)

    def delete(self, request, *args, **kwargs):
        scheme_account = get_object_or_404(SchemeAccount, id=kwargs['pk'])
        users = list(scheme_account.user_set.all())

        SchemeAccountEntry.objects.filter(scheme_account=scheme_account).delete()
        PaymentCardSchemeEntry.objects.filter(scheme_account=scheme_account).delete()
        scheme_account.is_deleted = True
        scheme_account.save()
        for user in users:
            if user.client_id == settings.BINK_CLIENT_ID:
                old_status = dict(scheme_account.STATUSES).get(scheme_account.status_key)
                analytics.update_scheme_account_attribute(scheme_account, user, old_status=old_status)

        return Response(status=status.HTTP_204_NO_CONTENT)


class UpdateUserConsent(UpdateAPIView):
    authentication_classes = (ServiceAuthentication,)
    queryset = UserConsent.objects.all()
    serializer_class = UpdateUserConsentSerializer

    def put(self, request, *args, **kwargs):
        if request.data.get('status') == ConsentStatus.FAILED:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data)
            serializer.is_valid(raise_exception=True)

            consent = self.get_object()
            consent.delete()
            return Response(serializer.data)
        else:
            return self.update(request, *args, **kwargs)


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
        queryset = self.request.channels_permit.scheme_account_query(SchemeAccount.objects)
        scheme_account = get_object_or_404(queryset, id=self.kwargs['pk'],
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
        permit = request.channels_permit
        queryset = permit.scheme_account_query(SchemeAccount.objects)
        scheme_account = get_object_or_404(queryset, id=self.kwargs['pk'], user_set__id=request.user.id)

        if permit.is_scheme_suspended(scheme_account.scheme_id):
            return Response({
                'error': 'This scheme is temporarily unavailable.'
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = LinkSchemeSerializer(data=request.data, context={'scheme_account': scheme_account,
                                                                      'user': request.user})

        serializer.is_valid(raise_exception=True)

        old_status = scheme_account.status

        response_data = self.link_account(serializer, scheme_account, request.user)
        scheme_account.save()

        if request.user.client_id == settings.BINK_CLIENT_ID:
            analytics.update_scheme_account_attribute(
                scheme_account,
                request.user,
                dict(scheme_account.STATUSES).get(old_status))

        out_serializer = ResponseLinkSerializer(response_data)

        # Update barcode on front end if we get one from linking
        response = out_serializer.data
        barcode = scheme_account.barcode
        if barcode:
            response['barcode'] = barcode

        return Response(response, status=status.HTTP_201_CREATED)


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
        channels_permit = self.request.channels_permit
        queryset = SchemeAccount.objects

        filter_by = {'user_set__id': self.request.user.id}

        if not self.request.user.is_tester:
            filter_by['scheme__test_scheme'] = False

        exclude_by = {}
        suspended_schemes = Scheme.objects.filter(
            schemebundleassociation__bundle=channels_permit.bundle,
            schemebundleassociation__status=SchemeBundleAssociation.SUSPENDED,
        )
        if suspended_schemes:
            exclude_by = {
                'scheme__in': suspended_schemes,
                'status__in': SchemeAccount.JOIN_ACTION_REQUIRED
            }

        return channels_permit.scheme_account_query(queryset.filter(**filter_by).exclude(**exclude_by))

    def post(self, request, *args, **kwargs):
        """
        Create a new scheme account within the users wallet.<br>
        This does not log into the loyalty scheme end site.
        """
        if not request.channels_permit.is_scheme_available(int(self.request.data['scheme'])):
            return Response(
                "Not Found",
                status=status.HTTP_404_NOT_FOUND,
            )

        _, response, _ = self.create_account(request.data, request.user)
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

        if user.client_id == settings.BINK_CLIENT_ID:
            analytics.update_scheme_account_attribute(account, user)

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

        # serialize the account for the response.
        serializer = GetSchemeAccountSerializer(instance=account, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UpdateSchemeAccountStatus(GenericAPIView):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)
    serializer_class = StatusSerializer

    def post(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS
        """

        scheme_account_id = int(kwargs['pk'])
        journey = request.data.get('journey')
        new_status_code = int(request.data['status'])
        if new_status_code not in [status_code[0] for status_code in SchemeAccount.STATUSES]:
            raise serializers.ValidationError('Invalid status code sent.')

        scheme_account = get_object_or_404(SchemeAccount, id=scheme_account_id)

        pending_statuses = (SchemeAccount.JOIN_ASYNC_IN_PROGRESS, SchemeAccount.JOIN_IN_PROGRESS,
                            SchemeAccount.PENDING, SchemeAccount.PENDING_MANUAL_CHECK)

        if new_status_code is SchemeAccount.ACTIVE:
            Payment.process_payment_success(scheme_account)
        elif new_status_code not in pending_statuses:
            Payment.process_payment_void(scheme_account)

        # method that sends data to Mnemosyne
        self.send_to_intercom(new_status_code, scheme_account)

        scheme_account.status = new_status_code
        scheme_account.save(update_fields=['status'])

        self.process_active_accounts(scheme_account, journey, new_status_code)

        return Response({
            'id': scheme_account.id,
            'status': new_status_code
        })

    def process_active_accounts(self, scheme_account, journey, new_status_code):
        if journey == 'join' and new_status_code == SchemeAccount.ACTIVE:
            scheme = scheme_account.scheme
            join_date = timezone.now()
            scheme_account.join_date = join_date
            scheme_account.save()
            async_join_journey_fetch_balance_and_update_status.delay(scheme_account.id)

            if scheme.tier in Scheme.TRANSACTION_MATCHING_TIERS:
                self.notify_rollback_transactions(scheme.slug, scheme_account, join_date)

        elif new_status_code == SchemeAccount.ACTIVE and not (scheme_account.link_date or scheme_account.join_date):
            date_time_now = timezone.now()
            scheme_slug = scheme_account.scheme.slug

            scheme_account.link_date = date_time_now
            scheme_account.save(update_fields=['link_date'])

            if scheme_slug in settings.SCHEMES_COLLECTING_METRICS:
                send_merchant_metrics_for_link_delete.delay(scheme_account.id, scheme_slug, date_time_now, 'link')

    def send_to_intercom(self, new_status_code, scheme_account):
        try:
            # use the more accurate user_set if provided
            user_set_from_midas = self.request.data['user_info']['user_set']
            user_ids = [int(user_id) for user_id in user_set_from_midas.split(',')]
        except KeyError:
            user_ids = [user.id for user in scheme_account.user_set.all()]

        for user_id in user_ids:
            user = CustomUser.objects.get(id=user_id)

            if user.client_id == settings.BINK_CLIENT_ID:
                if 'event_name' in self.request.data:
                    analytics.post_event(
                        user,
                        self.request.data['event_name'],
                        metadata=self.request.data['metadata'],
                        to_intercom=True
                    )

                if new_status_code != scheme_account.status:
                    analytics.update_scheme_account_attribute_new_status(
                        scheme_account,
                        user,
                        dict(scheme_account.STATUSES).get(new_status_code))

    @staticmethod
    def notify_rollback_transactions(scheme_slug: str, scheme_account: SchemeAccount, join_date: 'datetime'):
        if settings.ROLLBACK_TRANSACTIONS_URL:
            user_id = scheme_account.get_transaction_matching_user_id()
            payment_cards = PaymentCardAccount.objects.values('token').filter(user_set__id=user_id).all()
            data = json.dumps({
                'date_joined': join_date.date().isoformat(),
                'scheme_provider': scheme_slug,
                'payment_card_token': [card['token'] for card in payment_cards],
                'user_id': user_id,
                'credentials': scheme_account.credentials(),
                'loyalty_card_id': scheme_account.third_party_identifier,
                'scheme_account_id': scheme_account.id,
            })
            headers = {
                'Content-Type': "application/json",
                'Authorization': "token " + settings.SERVICE_API_KEY,
            }
            try:
                resp = requests.post(settings.ROLLBACK_TRANSACTIONS_URL + '/transaction_info/post_join', data=data,
                                     headers=headers)
                resp.raise_for_status()
            except requests.exceptions.RequestException:
                logging.exception('Failed to send join data to thanatos.')
                if settings.HERMES_SENTRY_DSN:
                    sentry_sdk.capture_exception()


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


class SchemeAccountsCredentials(RetrieveAPIView, UpdateCredentialsMixin):
    """
    DO NOT USE - NOT FOR APP ACCESS
    """
    authentication_classes = (JwtAuthentication, ServiceAuthentication)
    serializer_class = SchemeAccountCredentialsSerializer

    def get_queryset(self):
        queryset = SchemeAccount.objects
        if self.request.user.uid != 'api_user':
            query = {'user_set__id': self.request.user.id}
            if not self.request.user.is_tester:
                query['scheme__test_scheme'] = False

            queryset = queryset.filter(**query)
        return self.request.channels_permit.scheme_account_query(queryset)

    def put(self, request, *args, **kwargs):
        """
        Update / Create credentials for loyalty scheme login
        ---
        """
        account = self.get_object()
        return Response(self.update_credentials(account, request.data), status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        """
        Delete scheme credential answers from a scheme account
        ---
        parameters:
          - name: all
            required: false
            description: boolean, True will delete all scheme credential answers
          - name: keep_card_number
            required: false
            description: boolean, if All is not passed, True will delete all credentials apart from card_number
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
        credential_list = scheme_account.schemeaccountcredentialanswer_set
        answers_to_delete = set()

        if request_data.get('all'):
            answers_to_delete.update(credential_list.all())
            return answers_to_delete

        elif request_data.get('keep_card_number'):
            card_number = scheme_account.card_number
            if card_number:
                credential_list = credential_list.exclude(answer=card_number)

            answers_to_delete.update(credential_list.all())
            return answers_to_delete

        for credential_property in request_data.get('property_list'):
            try:
                questions = getattr(scheme_account.scheme, credential_property)
                answers_to_delete.update(self.get_answers_from_question_list(scheme_account, questions))
            except AttributeError:
                return self.invalid_data_response(credential_property)

        scheme_account_types = [answer.question.type for answer in credential_list.all()]
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
        host_scheme = Scheme.objects.get(pk=kwargs['scheme_id'])
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


class Join(SchemeAccountJoinMixin, SwappableSerializerMixin, GenericAPIView):
    override_serializer_classes = {
        'POST': JoinSerializer,
    }

    def post(self, request, *args, **kwargs):
        """
        Create a new scheme account,
        Register a new loyalty account on the requested scheme,
        Link the newly created loyalty account with the created scheme account.
        """
        scheme_id = int(kwargs['pk'])
        if not self.request.channels_permit.is_scheme_available(scheme_id):
            raise NotFound('Scheme does not exist.')

        message, status_code, _ = self.handle_join_request(request.data, request.user, scheme_id,
                                                           request.channels_permit)
        return Response(message, status=status_code)

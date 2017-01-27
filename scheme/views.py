import csv
import uuid
import requests
from django.http import HttpResponseBadRequest
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext
from django.utils import timezone
from rest_framework.generics import (RetrieveAPIView, ListAPIView, GenericAPIView,
                                     get_object_or_404, ListCreateAPIView)
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from scheme.forms import CSVUploadForm
from scheme.models import (Scheme, SchemeAccount, SchemeAccountCredentialAnswer, Exchange, SchemeImage,
                           SchemeAccountImage)
from scheme.serializers import (SchemeSerializer, LinkSchemeSerializer, ListSchemeAccountSerializer,
                                CreateSchemeAccountSerializer, GetSchemeAccountSerializer,
                                SchemeAccountCredentialsSerializer, SchemeAccountIdsSerializer,
                                StatusSerializer, ResponseLinkSerializer,
                                SchemeAccountSummarySerializer, ResponseSchemeAccountAndBalanceSerializer,
                                SchemeAnswerSerializer, DonorSchemeSerializer, ReferenceImageSerializer,
                                QuerySchemeAccountSerializer)
from user.models import UserSetting
from rest_framework import status
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.reverse import reverse
from user.authentication import ServiceAuthentication, AllowService, JwtAuthentication
from django.db import transaction
from scheme.account_status_summary import scheme_account_status_data
from io import StringIO
from django.conf import settings
from user.models import CustomUser


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
        return Response(status=status.HTTP_204_NO_CONTENT)


class LinkCredentials(GenericAPIView):
    serializer_class = SchemeAnswerSerializer
    override_serializer_classes = {
        'PUT': SchemeAnswerSerializer,
        'POST': LinkSchemeSerializer,
        'OPTIONS': LinkSchemeSerializer,
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
        serializer = LinkSchemeSerializer(data=request.data, context={'scheme_account': scheme_account})
        response_data = self.link_account(serializer, scheme_account)
        out_serializer = ResponseLinkSerializer(response_data)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)

    @staticmethod
    def link_account(serializer, scheme_account):
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        for answer_type, answer in data.items():
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(answer_type),
                scheme_account=scheme_account, defaults={'answer': answer})
        response_data = {
            'balance': scheme_account.get_midas_balance(),
            'status': scheme_account.status,
            'status_name': scheme_account.status_name
        }
        response_data.update(serializer.data)
        return response_data


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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            try:
                scheme_account = SchemeAccount.objects.get(
                    user=request.user,
                    scheme_id=data['scheme'],
                    status=SchemeAccount.JOIN
                )

                scheme_account.order = data['order']
                scheme_account.status = SchemeAccount.WALLET_ONLY
                scheme_account.save()
            except SchemeAccount.DoesNotExist:
                scheme_account = SchemeAccount.objects.create(
                    user=request.user,
                    scheme_id=data['scheme'],
                    order=data['order'],
                    status=SchemeAccount.WALLET_ONLY
                )

            SchemeAccountCredentialAnswer.objects.create(
                scheme_account=scheme_account,
                question=scheme_account.question(serializer.context['answer_type']),
                answer=data[serializer.context['answer_type']],
            )
        data['id'] = scheme_account.id
        return Response(data, status=status.HTTP_201_CREATED,
                        headers={'Location': reverse('retrieve_account', args=[scheme_account.id], request=request)})


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
    return render_to_response('admin/csv_upload_form.html', context, context_instance=RequestContext(request))


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
        donor_scheme_accounts = scheme_accounts.filter(scheme__in=exchanges.values('donor_scheme'))

        scheme_accounts_serializer = ListSchemeAccountSerializer(donor_scheme_accounts, many=True)
        exchange_serializer = DonorSchemeSerializer(exchanges, many=True)

        return_data = []

        for (s, e) in zip(scheme_accounts_serializer.data, exchange_serializer.data):
            data = e
            data['scheme_account_id'] = s['id']
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

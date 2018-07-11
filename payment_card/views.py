import csv
import json
from io import StringIO

import arrow
import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import View
from raven.contrib.django.raven_compat.models import client as sentry
from rest_framework import generics, serializers as rest_framework_serializers, status
from rest_framework.generics import GenericAPIView, RetrieveUpdateDestroyAPIView, get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from intercom import intercom_api
from payment_card import metis, serializers
from payment_card.forms import CSVUploadForm
from payment_card.models import PaymentCard, PaymentCardAccount, PaymentCardAccountImage, ProviderStatusMapping
from payment_card.serializers import PaymentCardClientSerializer
from scheme.models import Scheme, SchemeAccount
from ubiquity.models import PaymentCardAccountEntry, SchemeAccountEntry
from user.authentication import AllowService, JwtAuthentication, ServiceAuthentication
from user.models import ClientApplication, Organisation


class ListPaymentCard(generics.ListAPIView):
    """
    List of supported payment cards.
    """
    queryset = PaymentCard.objects
    serializer_class = serializers.PaymentCardSerializer


class PaymentCardAccountQuery(APIView):
    authentication_classes = (ServiceAuthentication,)

    def get(self, request):
        try:
            queryset = PaymentCardAccount.objects.filter(**dict(request.query_params.items()))
        except Exception as e:
            response = {
                'exception_class': e.__class__.__name__,
                'exception_args': e.args
            }
            return Response(response, status=status.HTTP_400_BAD_REQUEST)
        serializer = serializers.QueryPaymentCardAccountSerializer(instance=queryset, many=True)
        return Response(serializer.data)


class RetrievePaymentCardAccount(RetrieveUpdateDestroyAPIView):
    """
    Retrieve and update payment card information.
    """
    queryset = PaymentCardAccount.objects
    serializer_class = serializers.PaymentCardAccountSerializer

    def get_queryset(self):
        user_id = self.request.user.id
        return self.queryset.filter(user_set__id=user_id)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = serializers.UpdatePaymentCardAccountSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        try:
            intercom_api.update_payment_account_custom_attribute(settings.INTERCOM_TOKEN, instance, request.user)
        except intercom_api.IntercomException:
            sentry.captureException()

        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        """
        Marks a paymentcardaccount as deleted.
        Responds with a 204 - No content.
        ---
        omit_serializer: True
        """
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()

        requests.delete(settings.METIS_URL + '/payment_service/payment_card', json={
            'payment_token': instance.psp_token,
            'card_token': instance.token,
            'partner_slug': instance.payment_card.slug,
            'id': instance.id,
            'date': arrow.get(instance.created).timestamp}, headers={
            'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
            'Content-Type': 'application/json'})

        try:
            intercom_api.update_payment_account_custom_attribute(settings.INTERCOM_TOKEN, instance, request.user)
        except intercom_api.IntercomException:
            sentry.captureException()

        return Response(status=status.HTTP_204_NO_CONTENT)


class ListCreatePaymentCardAccount(APIView):
    serializer_class = serializers.PaymentCardAccountSerializer

    def get(self, request):
        """List payment card accounts
        ---
        response_serializer: serializers.PaymentCardAccountSerializer
        """
        accounts = [self.serializer_class(instance=account).data for account in
                    PaymentCardAccount.objects.filter(user_set__id=request.user.id)]
        return Response(accounts, status=200)

    def post(self, request):
        message, status_code, _ = self.create_payment_card_account(request.data, request.user)
        return Response(message, status=status_code)

    def create_payment_card_account(self, data, user):
        """Add a payment card account
        ---
        request_serializer: serializers.PaymentCardAccountSerializer
        response_serializer: serializers.PaymentCardAccountSerializer
        responseMessages:
            - code: 400
              message: Error code 400 is indicative of serializer errors. The error response will show more information.
            - code: 403
              message: A payment card account by that fingerprint and expiry already exists.
        """

        serializer = serializers.CreatePaymentCardAccountSerializer(data=data)
        if serializer.is_valid():
            data = serializer.validated_data
            try:
                account = PaymentCardAccount.objects.get(fingerprint=data['fingerprint'],
                                                         expiry_month=data['expiry_month'],
                                                         expiry_year=data['expiry_year'])
            except PaymentCardAccount.DoesNotExist:
                account = PaymentCardAccount(**data)
                result = self._create_payment_card_account(account, user)
                if not isinstance(result, PaymentCardAccount):
                    return result

                self.apply_barclays_images(account)

            else:
                # if the payment card exists already in another user, link it to this user and import all the scheme
                # accounts currently linked to it.
                if account.is_deleted:
                    account.is_deleted = False
                    account.save()

                PaymentCardAccountEntry.objects.get_or_create(user=user, payment_card_account=account)
                for scheme_account in account.scheme_account_set.all():
                    SchemeAccountEntry.objects.get_or_create(user=user, scheme_account=scheme_account)

            try:
                intercom_api.update_payment_account_custom_attribute(settings.INTERCOM_TOKEN, account, user)
            except intercom_api.IntercomException:
                sentry.captureException()

            response_serializer = serializers.PaymentCardAccountSerializer(instance=account)
            return response_serializer.data, status.HTTP_201_CREATED, account
        return serializer.errors, status.HTTP_400_BAD_REQUEST, None

    @staticmethod
    def _create_payment_card_account(account, user):
        if account.payment_card.system == PaymentCard.MASTERCARD:
            # get the oldest matching account
            old_account = PaymentCardAccount.all_objects.filter(
                fingerprint=account.fingerprint).order_by('-created').first()

            if old_account:
                return ListCreatePaymentCardAccount.supercede_old_card(account, old_account, user)
        account.save()
        PaymentCardAccountEntry.objects.create(user=user, payment_card_account=account)
        metis.enrol_new_payment_card(account)
        return account

    @staticmethod
    def supercede_old_card(account, old_account, user):
        # if the clients are the same but the users don't match, reject the card.
        if not old_account.user_set.filter(pk=user.pk).exists() and old_account.user_set.filter(
                client=user.client).exists():
            return Response({'error': 'Fingerprint is already in use by another user.',
                             'code': '403'}, status=status.HTTP_403_FORBIDDEN)

        account.token = old_account.token
        account.psp_token = old_account.psp_token

        if old_account.is_deleted:
            account.save()
            metis.enrol_existing_payment_card(account)
        else:
            account.status = old_account.status
            account.save()

            # only delete the old card if it's on the same app
            if old_account.user_set.filter(client=user.client).exists():
                old_account.is_deleted = True
                old_account.save()

        return account

    @staticmethod
    def apply_barclays_images(account):
        # if the card is a barclaycard, attach relevant placeholder images to signify that we can't auto-collect.
        if account.pan_start in settings.BARCLAYS_BINS:
            barclays_offer_image = PaymentCardAccountImage.objects.get(description='barclays',
                                                                       image_type_code=6)
            barclays_offer_image.payment_card_accounts.add(account)

            try:
                barclays_hero_image = PaymentCardAccountImage.objects.get(description='barclays',
                                                                          image_type_code=0,
                                                                          payment_card=account.payment_card)
            except PaymentCardAccountImage.DoesNotExist:
                # not a barclays card that we have an image for, so don't add it.
                pass
            else:
                barclays_hero_image.payment_card_accounts.add(account)


class RetrievePaymentCardSchemeAccounts(generics.ListAPIView):
    serializer_class = serializers.PaymentCardSchemeAccountSerializer

    # TODO: Remove JwtAuthentication before pushing to production.
    authentication_classes = (JwtAuthentication, ServiceAuthentication)

    def get_queryset(self):
        token = self.kwargs.get('token')
        payment_card_account = PaymentCardAccount.objects.filter(token=token).first()
        scheme_account_set = payment_card_account.scheme_account_set.all()

        return [
            {
                'scheme_id': scheme.scheme_id,
                'scheme_account_id': scheme.id
            }
            for scheme in list(scheme_account_set)
        ]


class RetrieveLoyaltyID(View):
    authentication_classes = ServiceAuthentication,

    @staticmethod
    def post(request, scheme_slug):
        response_data = []
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        payment_card_tokens = body['payment_cards']
        scheme = get_object_or_404(Scheme, slug=scheme_slug)
        for payment_card_token in payment_card_tokens:
            payment_card_entry = PaymentCardAccountEntry.objects.filter(
                payment_card_account__token=payment_card_token).first()
            if payment_card_entry:
                payment_card = payment_card_entry.payment_card_account
                try:
                    scheme_account_entry = SchemeAccountEntry.objects.get(user=payment_card_entry.user,
                                                                          scheme_account__scheme=scheme)
                except ObjectDoesNotExist:
                    # the user was matched but is not registered in that scheme
                    response_data.append({payment_card_token: None})
                else:
                    scheme_account = scheme_account_entry.scheme_account
                    response_data.append({
                        payment_card.token: scheme_account.third_party_identifier,
                        'scheme_account_id': scheme_account.id
                    })
            else:
                response_data.append({payment_card_token: None})
        return JsonResponse(response_data, safe=False)


class RetrievePaymentCardUserInfo(View):
    authentication_classes = ServiceAuthentication,

    @staticmethod
    def post(request, scheme_slug):
        response_data = {}
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        payment_card_tokens = body['payment_cards']
        scheme = get_object_or_404(Scheme, slug=scheme_slug)
        for payment_card_token in payment_card_tokens:
            payment_card_entries = PaymentCardAccountEntry.objects.filter(
                payment_card_account__token=payment_card_token)

            # if there's no payment card for this token, leave it out of the returned data.
            if not payment_card_entries.exists():
                continue

            scheme_accounts = SchemeAccount.objects.filter(scheme=scheme,
                                                           status=SchemeAccount.ACTIVE,
                                                           user_set__id__in=(p.user.id for p in payment_card_entries))
            if scheme_accounts.exists():
                scheme_account = scheme_accounts.order_by('created').first()
                response_data[payment_card_token] = {
                    'loyalty_id': scheme_account.third_party_identifier,
                    'scheme_account_id': scheme_account.id,
                    'user_set': [user.id for user in scheme_account.user_set.all()],
                    'credentials': scheme_account.credentials()
                }
            else:
                # the user was matched but is not registered in that scheme
                response_data[payment_card_token] = {
                    'loyalty_id': None,
                    'scheme_account_id': None,
                    'user_id': payment_card_entries.first().user.id,
                    'credentials': '',
                }

            active_card = next(
                (x for x in payment_card_entries if x.payment_card_account.status == PaymentCardAccount.ACTIVE), None)
            if active_card:
                response_data[payment_card_token]['card_information'] = {
                    'first_six': active_card.payment_card_account.pan_start,
                    'last_four': active_card.payment_card_account.pan_end
                }

        return JsonResponse(response_data, safe=False)


class UpdatePaymentCardAccountStatus(GenericAPIView):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)
    serializer_class = serializers.PaymentCardAccountStatusSerializer

    def put(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS
        """
        id = request.data.get('id', None)
        token = request.data.get('token', None)

        if not (id or token):
            raise rest_framework_serializers.ValidationError('No ID or token provided.')

        new_status_code = int(request.data['status'])
        if new_status_code not in [status_code[0] for status_code in PaymentCardAccount.STATUSES]:
            raise rest_framework_serializers.ValidationError('Invalid status code sent.')

        if id:
            payment_card_account = get_object_or_404(PaymentCardAccount, id=int(id))
        else:
            payment_card_account = get_object_or_404(PaymentCardAccount, token=token)

        if new_status_code != payment_card_account.status:
            payment_card_account.status = new_status_code
            payment_card_account.save()

        try:
            intercom_api.update_payment_account_custom_attribute(settings.INTERCOM_TOKEN, payment_card_account,
                                                                 request.user)
        except intercom_api.IntercomException:
            sentry.captureException()

        return Response({
            'id': payment_card_account.id,
            'status': new_status_code
        })


class ListProviderStatusMappings(generics.ListAPIView):
    """
    List available provider-bink status mappings.
    """
    authentication_classes = (ServiceAuthentication,)
    serializer_class = serializers.ProviderStatusMappingSerializer

    def get_queryset(self):
        slug = self.kwargs['slug']

        # we need to provide callers with the UNKNOWN error code for any error not in the returned dictionary.
        # look for an UNKNOWN status card for this provider...
        if not ProviderStatusMapping.objects.filter(provider__slug=slug,
                                                    bink_status_code=PaymentCardAccount.UNKNOWN).exists():
            # there isn't one yet, so add it.
            ProviderStatusMapping(provider=PaymentCard.objects.get(slug=slug),
                                  provider_status_code='BINK_UNKNOWN',
                                  bink_status_code=PaymentCardAccount.UNKNOWN).save()

        return ProviderStatusMapping.objects.filter(provider__slug=slug)


def csv_upload(request):
    # If we had a POST then get the request post values.
    form = CSVUploadForm()
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            payment_card = PaymentCard.objects.get(id=int(request.POST['scheme']))
            uploaded_file = StringIO(request.FILES['emails'].file.read().decode())
            # 6 = magic number for personal offers
            image_instance = PaymentCardAccountImage(payment_card=payment_card, start_date=timezone.now(),
                                                     image_type_code=6, order=0)
            image_instance.save()
            csvreader = csv.reader(uploaded_file, delimiter=',', quotechar='"')
            for row in csvreader:
                for email in row:
                    payment_card_account_entry = PaymentCardAccountEntry.objects.filter(
                        user__email=email.lstrip(),
                        payment_card_account__payment_card=payment_card)
                    if payment_card_account_entry:
                        image_instance.payment_card_accounts.add(
                            payment_card_account_entry.first().payment_card_account
                        )
                    else:
                        image_instance.delete()
                        return HttpResponseBadRequest()

            image_instance.save()

            return redirect('/admin/payment_card/paymentaccountimage/{}'.format(image_instance.id))

    context = {'form': form}
    return render(request, 'admin/csv_upload_form.html', context)


class AuthTransactionView(generics.CreateAPIView):
    authentication_classes = (ServiceAuthentication,)
    permission_classes = (AllowService,)
    serializer_class = serializers.AuthTransactionSerializer


class ListPaymentCardClientApplication(generics.ListAPIView):
    authentication_classes = (ServiceAuthentication,)
    permission_classes = (AllowService,)
    serializer_class = PaymentCardClientSerializer

    def get_queryset(self):
        clients = []
        for system in PaymentCard.SYSTEMS:
            try:
                organisation = Organisation.objects.get(name=system[1])
                client = ClientApplication.objects.get(organisation=organisation, name__contains='Auth Transactions')
                clients.append(client)
            except (Organisation.DoesNotExist, ClientApplication.DoesNotExist):
                pass

        return clients

import csv
import json
import requests
from django.http import HttpResponseBadRequest, JsonResponse
from io import StringIO
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render_to_response
from django.template import RequestContext
from django.utils import timezone
from django.views.generic import View
from django.conf import settings
from rest_framework import generics, status
# from rest_framework import serializers
from rest_framework.generics import GenericAPIView, RetrieveUpdateDestroyAPIView, get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from payment_card.forms import CSVUploadForm
from payment_card.models import PaymentCard, PaymentCardAccount, PaymentCardAccountImage, ProviderStatusMapping
from payment_card.payment_card_scheme_accounts import payment_card_scheme_accounts
from payment_card import serializers
from scheme.models import Scheme, SchemeAccount
from user.authentication import AllowService, JwtAuthentication, ServiceAuthentication
import arrow


class ListPaymentCard(generics.ListAPIView):
    """
    List of supported payment cards.
    """
    queryset = PaymentCard.objects
    serializer_class = serializers.PaymentCardSerializer


class RetrievePaymentCardAccount(RetrieveUpdateDestroyAPIView):
    """
    Retrieve and update payment card information.
    """
    queryset = PaymentCardAccount.objects
    serializer_class = serializers.PaymentCardAccountSerializer

    def get_queryset(self):
        user = self.request.user
        return PaymentCardAccount.objects.filter(user=user)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = serializers.UpdatePaymentCardAccountSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
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

        return Response(status=status.HTTP_204_NO_CONTENT)


class ListCreatePaymentCardAccount(APIView):

    def get(self, request):
        """List payment card accounts
        ---
        response_serializer: PaymentCardAccountSerializer
        """
        accounts = [serializers.PaymentCardAccountSerializer(instance=account).data for account in
                    PaymentCardAccount.objects.filter(user=request.user)]
        return Response(accounts, status=200)

    def post(self, request):
        """Add a payment card account
        ---
        request_serializer: PaymentCardAccountSerializer
        response_serializer: PaymentCardAccountSerializer
        responseMessages:
            - code: 400
              message: Error code 400 is indicative of serializer errors. The error response will show more information.
            - code: 403
              message: A payment card account by that fingerprint and expiry already exists.
        """
        request.data['user'] = request.user.id

        # iOS bug fix: only capture the last four digits of the pan_end (they send us five.)
        request.data['pan_end'] = request.data['pan_end'][-4:]

        serializer = serializers.CreatePaymentCardAccountSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data

            # make sure we're not creating a duplicate card
            accounts = PaymentCardAccount.objects.filter(fingerprint=data['fingerprint'],
                                                         expiry_month=data['expiry_month'],
                                                         expiry_year=data['expiry_year'])

            for account in accounts:
                if not account.is_deleted:
                    return Response({'error': 'A payment card account by that fingerprint and expiry already exists.',
                                     'code': '403'}, status=status.HTTP_403_FORBIDDEN)

            account = PaymentCardAccount(**data)
            account.save()

            requests.post(settings.METIS_URL + '/payment_service/payment_card', json={
                'payment_token': account.psp_token,
                'card_token': account.token,
                'partner_slug': account.payment_card.slug,
                'id': account.id,
                'date': arrow.get(account.created).timestamp}, headers={
                    'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                    'Content-Type': 'application/json'})

            # if the card is a barclaycard, attach relevant placeholder images to signify that we can't auto-collect.
            if account.pan_start in settings.BARCLAYS_BINS:
                barclays_offer_image = PaymentCardAccountImage.objects.get(description='barclays',
                                                                           image_type_code=2)
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

            response_serializer = serializers.PaymentCardAccountSerializer(instance=account)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RetrievePaymentCardSchemeAccounts(generics.ListAPIView):
    serializer_class = serializers.PaymentCardSchemeAccountSerializer

    # TODO: Remove JwtAuthentication before pushing to production.
    authentication_classes = (JwtAuthentication, ServiceAuthentication)

    def get_queryset(self):
        token = self.kwargs.get('token')
        data = payment_card_scheme_accounts(token)
        return data


class RetrieveLoyaltyID(View):
    authentication_classes = ServiceAuthentication,

    def post(self, request, scheme_slug):
        response_data = []
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        payment_card_tokens = body['payment_cards']
        scheme = get_object_or_404(Scheme, slug=scheme_slug)
        for payment_card_token in payment_card_tokens:
            payment_card = PaymentCardAccount.objects.filter(token=payment_card_token).first()
            if payment_card:
                try:
                    scheme_account = SchemeAccount.objects.get(user=payment_card.user, scheme=scheme)
                except ObjectDoesNotExist:
                    # the user was matched but is not registered in that scheme
                    response_data.append({payment_card_token: None})
                else:
                    response_data.append({
                        payment_card.token: scheme_account.third_party_identifier,
                        'scheme_account_id': scheme_account.id
                    })
            else:
                response_data.append({payment_card_token: None})
        return JsonResponse(response_data, safe=False)


class RetrievePaymentCardUserInfo(View):
    authentication_classes = ServiceAuthentication,

    def post(self, request, scheme_slug):
        response_data = {}
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        payment_card_tokens = body['payment_cards']
        scheme = get_object_or_404(Scheme, slug=scheme_slug)
        for payment_card_token in payment_card_tokens:
            payment_card = PaymentCardAccount.objects.filter(token=payment_card_token).first()
            if payment_card:
                try:
                    scheme_account = SchemeAccount.objects.get(user=payment_card.user, scheme=scheme)
                except ObjectDoesNotExist:
                    # the user was matched but is not registered in that scheme
                    response_data[payment_card_token] = {
                        'loyalty_id': None,
                        'scheme_account_id': None,
                        'user_id': payment_card.user_id,
                        'credentials': ''
                    }
                else:
                    if scheme_account.status == SchemeAccount.ACTIVE:
                        response_data[payment_card_token] = {
                            'loyalty_id': scheme_account.third_party_identifier,
                            'scheme_account_id': scheme_account.id,
                            'user_id': payment_card.user_id,
                            'credentials': scheme_account.credentials()
                        }
            else:
                # if we don't find a payment_card / user we don't insert the token
                # in the result to signify that something must be wrong.
                pass
        return JsonResponse(response_data, safe=False)


class UpdatePaymentCardAccountStatus(GenericAPIView):
    permission_classes = (AllowService,)
    authentication_classes = (ServiceAuthentication,)
    serializer_class = serializers.PaymentCardAccountStatusSerializer

    def put(self, request, *args, **kwargs):
        """
        DO NOT USE - NOT FOR APP ACCESS
        """
        new_status_code = int(request.data['status'])
        if new_status_code not in [status_code[0] for status_code in PaymentCardAccount.STATUSES]:
            raise serializers.ValidationError('Invalid status code sent.')

        payment_card_account = get_object_or_404(PaymentCardAccount, id=int(kwargs['pk']))
        if new_status_code != payment_card_account.status:
            payment_card_account.status = new_status_code
            payment_card_account.save()

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
                    payment_card_account = PaymentCardAccount.objects.filter(user__email=email.lstrip(),
                                                                             payment_card=payment_card)
                    if payment_card_account:
                        image_instance.payment_card_accounts.add(payment_card_account.first())
                    else:
                        image_instance.delete()
                        return HttpResponseBadRequest()

            image_instance.save()

            return redirect('/admin/payment_card/paymentaccountimage/{}'.format(image_instance.id))

    context = {'form': form}
    return render_to_response('admin/csv_upload_form.html', context, context_instance=RequestContext(request))

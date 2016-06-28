import csv
import json
from io import StringIO
from django.http import JsonResponse, HttpResponseBadRequest
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext
from django.utils import timezone
from django.views.generic import View
from rest_framework.views import APIView
from payment_card.forms import CSVUploadForm
from payment_card.payment_card_scheme_accounts import payment_card_scheme_accounts
from rest_framework import generics
from rest_framework.generics import RetrieveUpdateDestroyAPIView, ListAPIView, get_object_or_404
from payment_card.models import PaymentCardAccount, PaymentCard, PaymentCardAccountImageCriteria
from payment_card.serializers import (PaymentCardAccountSerializer, PaymentCardSerializer,
                                      PaymentCardSchemeAccountSerializer, UpdatePaymentCardAccountSerializer)
from rest_framework.response import Response
from rest_framework import status

from scheme.models import Scheme, SchemeAccount
from user.authentication import JwtAuthentication, ServiceAuthentication


class ListPaymentCard(generics.ListAPIView):
    """
    List of supported payment cards.
    """
    queryset = PaymentCard.objects
    serializer_class = PaymentCardSerializer


class RetrievePaymentCardAccount(RetrieveUpdateDestroyAPIView):
    """
    Retrieve and update payment card information.
    """
    queryset = PaymentCardAccount.objects
    serializer_class = PaymentCardAccountSerializer

    def get_queryset(self):
        user = self.request.user
        return PaymentCardAccount.objects.filter(user=user)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = UpdatePaymentCardAccountSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        """
        Marks a paymentcardaccount as deleted.
        Responds with a 204 - No content.
        """
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreatePaymentCardAccount(APIView):
    def post(self, request):
        request.data['user'] = request.user.id
        serializer = PaymentCardAccountSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data

            # make sure we're not creating a duplicate card
            accounts = PaymentCardAccount.objects.filter(fingerprint=data['fingerprint'],
                                                         expiry_month=data['expiry_month'],
                                                         expiry_year=data['expiry_year'])

            for account in accounts:
                if not account.is_deleted:
                    return Response({'error': 'a payment card account by that fingerprint and expiry already exists.',
                                     'code': '400'}, status=status.HTTP_400_BAD_REQUEST)

            account = PaymentCardAccount(**data)
            account.save()

            return Response(data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RetrievePaymentCardSchemeAccounts(ListAPIView):
    serializer_class = PaymentCardSchemeAccountSerializer

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
                    }
                else:
                    response_data[payment_card_token] = {
                        'loyalty_id': scheme_account.third_party_identifier,
                        'scheme_account_id': scheme_account.id,
                        'user_id': payment_card.user_id
                    }
            else:
                # if we don't find a payment_card / user we don't insert the token
                # in the result to signify that something must be wrong.
                pass
        return JsonResponse(response_data, safe=False)


def csv_upload(request):
    # If we had a POST then get the request post values.
    form = CSVUploadForm()
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            payment_card = PaymentCard.objects.get(id=int(request.POST['scheme']))
            uploaded_file = StringIO(request.FILES['emails'].file.read().decode())
            image_criteria_instance = PaymentCardAccountImageCriteria(payment_card=payment_card,
                                                                      start_date=timezone.now())
            image_criteria_instance.save()
            csvreader = csv.reader(uploaded_file, delimiter=',', quotechar='"')
            for row in csvreader:
                for email in row:
                    payment_card_account = PaymentCardAccount.objects.filter(user__email=email.lstrip(),
                                                                             payment_card=payment_card)
                    if payment_card_account:
                        image_criteria_instance.payment_card_accounts.add(payment_card_account.first())
                    else:
                        image_criteria_instance.delete()
                        return HttpResponseBadRequest()

            image_criteria_instance.save()

            return redirect('/admin/payment_card/paymentaccountimagecriteria/{}'.format(image_criteria_instance.id))

    context = {'form': form}
    return render_to_response('admin/csv_upload_form.html', context, context_instance=RequestContext(request))

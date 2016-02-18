from django.http import HttpResponse, JsonResponse
from django.views.generic import View
from rest_framework.views import APIView
from payment_card.payment_card_scheme_accounts import payment_card_scheme_accounts
from rest_framework import generics
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, ListAPIView, GenericAPIView
from payment_card.models import PaymentCardAccount, PaymentCard
from payment_card.serializers import PaymentCardAccountSerializer, PaymentCardSerializer, \
    PaymentCardSchemeAccountSerializer, UpdatePaymentCardAccountSerializer
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


class CreatePaymentCardAccount(ListCreateAPIView):
    """
    Create and retrieve users payment card information.
    """
    serializer_class = PaymentCardAccountSerializer

    def post(self, request, *args, **kwargs):
        request.data['user'] = request.user.id
        return super(CreatePaymentCardAccount, self).post(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        return PaymentCardAccount.objects.filter(user=user)


class RetrievePaymentCardSchemeAccounts(ListAPIView):
    serializer_class = PaymentCardSchemeAccountSerializer

    # TODO: Remove JwtAuthentication before pushing to production.
    authentication_classes = (JwtAuthentication, ServiceAuthentication)

    def get_queryset(self):
        token = self.kwargs.get('token')
        data = payment_card_scheme_accounts(token)
        return data


class RetrieveLoyaltyIDs(View):
    authentication_classes = ServiceAuthentication,

    def post(self, request):
        response_data = []
        payment_cards = [PaymentCardAccount.objects.get(token=pc) for pc in request.POST.getlist('payment_cards')]
        scheme_slug = request.POST['scheme']
        scheme = Scheme.objects.get(slug=scheme_slug)
        for payment_card in payment_cards:
            scheme_account = SchemeAccount.objects.get(user=payment_card.user, scheme=scheme)
            response_data.append({payment_card.token: scheme_account.third_party_identifier})
        return JsonResponse(response_data, safe=False)



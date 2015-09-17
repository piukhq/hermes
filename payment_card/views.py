from rest_framework import generics
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from payment_card.models import PaymentCardAccount, PaymentCard
from payment_card.serializers import PaymentCardAccountSerializer, PaymentCardSerializer


class ListPaymentCard(generics.ListAPIView):
    queryset = PaymentCard.objects
    serializer_class = PaymentCardSerializer


class RetrievePaymentCardAccount(RetrieveUpdateAPIView):
    queryset = PaymentCardAccount.objects
    serializer_class = PaymentCardAccountSerializer


class CreatePaymentCardAccount(CreateAPIView):
    serializer_class = PaymentCardAccountSerializer

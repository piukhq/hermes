from rest_framework import generics
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from payment_card.models import PaymentCardAccount, PaymentCard
from payment_card.serializers import PaymentCardAccountSerializer, PaymentCardSerializer
from rest_framework import status


class ListPaymentCard(generics.ListAPIView):
    queryset = PaymentCard.objects
    serializer_class = PaymentCardSerializer


class RetrievePaymentCardAccount(RetrieveUpdateAPIView):
    queryset = PaymentCardAccount.active_objects
    serializer_class = PaymentCardAccountSerializer

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status = PaymentCardAccount.DELETED
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreatePaymentCardAccount(CreateAPIView):
    serializer_class = PaymentCardAccountSerializer

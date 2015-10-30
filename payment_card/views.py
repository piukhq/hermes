from rest_framework import generics
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView, ListCreateAPIView
from rest_framework.response import Response
from payment_card.models import PaymentCardAccount, PaymentCard
from payment_card.serializers import PaymentCardAccountSerializer, PaymentCardSerializer
from rest_framework import status
from scheme.views import SwappableSerializerMixin


class ListPaymentCard(generics.ListAPIView):
    """
    List of supported payment cards.
    """
    queryset = PaymentCard.objects
    serializer_class = PaymentCardSerializer


class RetrievePaymentCardAccount(RetrieveUpdateAPIView):
    """
    Retrieve and update payment card information.
    """
    queryset = PaymentCardAccount.active_objects
    serializer_class = PaymentCardAccountSerializer

    def delete(self, request, *args, **kwargs):
        """
        Marks a users payment card as deleted.
        Responds with a 204 - No content.
        """
        instance = self.get_object()
        instance.status = PaymentCardAccount.DELETED
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
        return PaymentCardAccount.active_objects.filter(user=user)

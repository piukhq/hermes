from rest_framework import generics
from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from payment_card.models import PaymentCardAccount, PaymentCard
from payment_card.serializers import PaymentCardAccountSerializer, PaymentCardSerializer, \
    UpdatePaymentCardAccountSerializer


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

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = UpdatePaymentCardAccountSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


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

from rest_framework import generics
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from payment_card.models import PaymentCardAccount, PaymentCard
from payment_card.serializers import PaymentCardAccountSerializer, PaymentCardSerializer
from rest_framework import status
from user.authenticators import JwtAuthentication


class ListPaymentCard(generics.ListAPIView):
    authentication_classes = (JwtAuthentication,)
    permission_classes = (IsAuthenticated,)

    queryset = PaymentCard.objects
    serializer_class = PaymentCardSerializer


class RetrievePaymentCardAccount(RetrieveUpdateAPIView):
    authentication_classes = (JwtAuthentication,)
    permission_classes = (IsAuthenticated,)

    queryset = PaymentCardAccount.active_objects
    serializer_class = PaymentCardAccountSerializer

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status = PaymentCardAccount.DELETED
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreatePaymentCardAccount(CreateAPIView):
    authentication_classes = (JwtAuthentication,)
    permission_classes = (IsAuthenticated,)

    serializer_class = PaymentCardAccountSerializer

from collections import defaultdict

from rest_framework import generics
from rest_framework.response import Response

from order.serializers import OrderSerializer
from payment_card.models import PaymentCardAccount
from scheme.models import SchemeAccount
from user.authentication import JwtAuthentication

account_classes = {"scheme": SchemeAccount, "payment_card": PaymentCardAccount}


class OrderUpdate(generics.CreateAPIView):
    """
    Order resource, takes a list of OrderSerializers items
    ---
    POST:
        omit_parameters:
            - form
        parameters:
            - name: order_items
              type: list
              paramType: body
    """

    authentication_classes = (JwtAuthentication,)
    serializer_class = OrderSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, many=True)
        if serializer.is_valid():
            accounts = defaultdict(list)

            for obj in serializer.data:
                account_type = obj["type"]
                account_class = account_classes[account_type]
                accounts[account_type].append(account_class(id=obj["id"], order=obj["order"]))

            for account_type, objs in accounts.items():
                account_classes[account_type].objects.bulk_update(objs, ["order"])

            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

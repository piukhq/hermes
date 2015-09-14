from rest_framework import generics
from scheme.models import Scheme
from scheme.serializers import SchemeSerializer


class Schemes(generics.ListAPIView):
    queryset = Scheme.objects.filter(is_active=True)
    serializer_class = SchemeSerializer

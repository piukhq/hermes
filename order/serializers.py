from rest_framework import serializers


class OrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order = serializers.IntegerField()
    type = serializers.CharField()

from rest_framework import serializers
from core.serializers import LogEntrySerializer as ActivityLogSerializer

class TransactionVolumeSerializer(serializers.Serializer):
    date = serializers.DateField()
    inbound = serializers.IntegerField()
    outbound = serializers.IntegerField()
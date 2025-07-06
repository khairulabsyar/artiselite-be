from rest_framework import serializers

class TransactionVolumeSerializer(serializers.Serializer):
    """Serializer for daily transaction volume data."""
    date = serializers.DateField()
    inbound = serializers.IntegerField()
    outbound = serializers.IntegerField()
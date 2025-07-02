from rest_framework import serializers
from .models import Product

class ProductSerializer(serializers.ModelSerializer):
    reason = serializers.CharField(write_only=True, required=False, help_text="The reason for the inventory change.")

    """
    Serializer for the Product model.

    Converts Product model instances to JSON format and validates
    incoming data for creating or updating product instances.
    """
    class Meta:
        model = Product
        fields = [f.name for f in Product._meta.fields] + ['reason']
        read_only_fields = ('created_at', 'updated_at') # These are set by the system

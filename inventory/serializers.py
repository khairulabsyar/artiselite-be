from rest_framework import serializers
from .models import Product

class FileUploadSerializer(serializers.Serializer):
    """
    Serializer for handling file uploads.
    """
    file = serializers.FileField()

class ProductSerializer(serializers.ModelSerializer):
    reason = serializers.CharField(write_only=True, required=False, help_text="Reason for the inventory change.")

    """
    Serializer for the Product model.

    Converts Product model instances to JSON format and validates
    incoming data for creating or updating product instances.
    """
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'tags', 'description', 'category', 'quantity',
            'low_stock_threshold', 'is_archived', 'created_at', 'updated_at', 'reason'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

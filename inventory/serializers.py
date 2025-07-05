from django.db import transaction
from rest_framework import serializers

from .models import InventoryLog, Product


class FileUploadSerializer(serializers.Serializer):
    """
    Serializer for handling file uploads.
    """
    file = serializers.FileField()

class ProductSerializer(serializers.ModelSerializer):
    reason = serializers.CharField(write_only=True, required=False, help_text="Reason for the inventory change.")
    quantity = serializers.IntegerField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'tags', 'description', 'category', 'quantity',
            'low_stock_threshold', 'is_archived', 'created_at', 'updated_at', 'reason'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_quantity(self, value):
        """
        Ensure quantity is not negative.
        """
        if value < 0:
            raise serializers.ValidationError('Quantity cannot be negative.')
        return value

    @transaction.atomic
    def create(self, validated_data):
        """
        Create a product and log the initial inventory.
        The view passes `_user` and `_reason` via `serializer.save()` which adds them to validated_data.
        """
        user = validated_data.pop('_user', None)
        reason = validated_data.pop('_reason', 'Product created')
        
        product = Product.objects.create(**validated_data)
        
        if product.quantity != 0:
            InventoryLog.objects.create(
                product=product,
                user=user,
                quantity_change=product.quantity,
                new_quantity=product.quantity,
                reason=reason
            )
        return product

    @transaction.atomic
    def update(self, instance, validated_data):
        """
        Update a product and log the inventory change if quantity is modified.
        """
        user = validated_data.pop('_user', None)
        reason = validated_data.pop('_reason', 'Product updated')
        
        old_quantity = instance.quantity
        
        # DRF's ModelSerializer.update handles the field updates
        instance = super().update(instance, validated_data)
        
        new_quantity = instance.quantity
        
        if old_quantity != new_quantity:
            InventoryLog.objects.create(
                product=instance,
                user=user,
                quantity_change=new_quantity - old_quantity,
                new_quantity=new_quantity,
                reason=reason
            )
            
        return instance

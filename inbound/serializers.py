from rest_framework import serializers
from .models import Supplier, Inbound, InboundItem
from inventory.models import Product
from inventory.serializers import ProductSerializer

class SupplierSerializer(serializers.ModelSerializer):
    """Serializer for the Supplier model."""
    class Meta:
        model = Supplier
        fields = '__all__'

class InboundItemSerializer(serializers.ModelSerializer):
    """Serializer for individual items within an inbound shipment."""
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = InboundItem
        fields = ['id', 'product', 'product_id', 'quantity', 'unit_price']

class InboundSerializer(serializers.ModelSerializer):
    """Serializer for inbound shipments, handling nested items."""
    items = InboundItemSerializer(many=True)
    supplier = SupplierSerializer(read_only=True)
    supplier_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Inbound
        fields = ['id', 'supplier', 'supplier_id', 'inbound_date', 'status', 'notes', 'items', 'created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        inbound = Inbound.objects.create(**validated_data)
        for item_data in items_data:
            InboundItem.objects.create(inbound=inbound, **item_data)
        return inbound

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        instance = super().update(instance, validated_data)

        if items_data is not None:
            # Simple approach: clear existing items and add new ones
            instance.items.all().delete()
            for item_data in items_data:
                InboundItem.objects.create(inbound=instance, **item_data)

        return instance

class InboundBulkUploadSerializer(serializers.Serializer):
    """Serializer for bulk uploading inbound shipments from a file."""
    file = serializers.FileField()

    def validate_file(self, value):
        """Check if the uploaded file is a CSV or XLSX."""
        if not value.name.endswith(('.csv', '.xlsx')):
            raise serializers.ValidationError('Unsupported file format. Please upload a CSV or XLSX file.')
        return value

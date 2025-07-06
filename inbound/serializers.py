from inventory.models import Product
from inventory.serializers import ProductSerializer
from rest_framework import serializers

from .models import Inbound, InboundItem, Supplier


class SupplierSerializer(serializers.ModelSerializer):
    """Serializer for the Supplier model."""
    class Meta:
        model = Supplier
        fields = '__all__'

class InboundItemSerializer(serializers.ModelSerializer):
    """Serializer for individual items within an inbound shipment."""
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = InboundItem
        fields = ['id', 'product', 'product_id', 'quantity', 'unit_price']

class InboundSerializer(serializers.ModelSerializer):
    """Serializer for inbound shipments, handling nested items."""
    items = InboundItemSerializer(many=True)
    supplier = SupplierSerializer(read_only=True)
    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(), source='supplier', write_only=True
    )
    # Use ListField for handling multiple attachments
    uploaded_attachments = serializers.ListField(
        child=serializers.FileField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )

    class Meta:
        model = Inbound
        fields = ['id', 'supplier', 'supplier_id', 'inbound_date', 'status', 'notes', 'items', 'created_at', 'uploaded_attachments']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        validated_data.pop('uploaded_attachments', None) # Handled in view
        user = validated_data.pop('_user', None)
        reason = validated_data.pop('_reason', 'Inbound created via API.')

        inbound = Inbound(**validated_data)
        inbound.save(_user=user, _reason=reason)

        for item_data in items_data:
            InboundItem.objects.create(inbound=inbound, **item_data)
            
        return inbound

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        validated_data.pop('uploaded_attachments', None) # Handled in view
        user = validated_data.pop('_user', None)
        reason = validated_data.pop('_reason', 'Inbound updated via API.')

        # Update instance fields from validated_data
        instance.supplier = validated_data.get('supplier', instance.supplier)
        instance.inbound_date = validated_data.get('inbound_date', instance.inbound_date)
        instance.status = validated_data.get('status', instance.status)
        instance.notes = validated_data.get('notes', instance.notes)
        
        instance.save(_user=user, _reason=reason)

        if items_data is not None:
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

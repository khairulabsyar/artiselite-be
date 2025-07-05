from core.models import Attachment
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
    # Use a simple FileField for testing
    uploaded_attachments = serializers.FileField(
        max_length=1000, 
        allow_empty_file=False, 
        use_url=False,
        write_only=True,
        required=False
    )

    class Meta:
        model = Inbound
        fields = ['id', 'supplier', 'supplier_id', 'inbound_date', 'status', 'notes', 'items', 'created_at', 'uploaded_attachments']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        uploaded_attachments = validated_data.pop('uploaded_attachments', [])
        inbound = Inbound.objects.create(**validated_data)

        for item_data in items_data:
            InboundItem.objects.create(inbound=inbound, **item_data)
        
        for attachment_file in uploaded_attachments:
            Attachment.objects.create(content_object=inbound, file=attachment_file)
            
        return inbound

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        uploaded_attachments = validated_data.pop('uploaded_attachments', [])
        instance = super().update(instance, validated_data)

        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                InboundItem.objects.create(inbound=instance, **item_data)

        for attachment_file in uploaded_attachments:
            Attachment.objects.create(content_object=instance, file=attachment_file)

        return instance

class InboundBulkUploadSerializer(serializers.Serializer):
    """Serializer for bulk uploading inbound shipments from a file."""
    file = serializers.FileField()

    def validate_file(self, value):
        """Check if the uploaded file is a CSV or XLSX."""
        if not value.name.endswith(('.csv', '.xlsx')):
            raise serializers.ValidationError('Unsupported file format. Please upload a CSV or XLSX file.')
        return value

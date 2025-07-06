from core.serializers import AttachmentSerializer
from rest_framework import serializers

from .models import Customer, Outbound


class CustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for the Customer model.
    """
    class Meta:
        model = Customer
        fields = '__all__'

class OutboundSerializer(serializers.ModelSerializer):
    """
    Serializer for the Outbound model.
    """
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    uploaded_attachments = serializers.ListField(
        child=serializers.FileField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )

    class Meta:
        model = Outbound
        fields = [
            'id', 'customer', 'customer_name', 'product', 'product_name', 'quantity',
            'so_ref', 'outbound_date', 'status', 'notes', 'created_by',
            'created_at', 'updated_at', 'attachments', 'uploaded_attachments'
        ]
        read_only_fields = ('created_by', 'created_at', 'updated_at')

    def validate(self, data):
        """
        Check that the outbound quantity does not exceed the available product quantity.
        """
        product = data.get('product')
        quantity = data.get('quantity')

        if product and quantity:
            if product.quantity < quantity:
                raise serializers.ValidationError(
                    {'product': f"Not enough stock for {product.name}. Available: {product.quantity}, Requested: {quantity}"}
                )
        return data

    def create(self, validated_data):
        """
        Create a new Outbound instance, handling the _user and _reason kwargs.
        """
        user = validated_data.pop('_user', None)
        reason = validated_data.pop('_reason', 'Created via API')
        instance = Outbound.objects.create(**validated_data)
        # Manually call save to trigger the logic in the model's save method
        instance.save(_user=user, _reason=reason)
        return instance

    def update(self, instance, validated_data):
        """
        Update an existing Outbound instance, handling the _user and _reason kwargs.
        """
        user = validated_data.pop('_user', None)
        reason = validated_data.pop('_reason', 'Updated via API')

        # Standard update process
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(_user=user, _reason=reason)
        return instance

class OutboundBulkUploadSerializer(serializers.Serializer):
    """
    Serializer for bulk uploading outbound records from a file.
    """
    file = serializers.FileField()

    def validate_file(self, value):
        """
        Check if the uploaded file is a CSV or XLSX.
        """
        if not value.name.endswith(('.csv', '.xlsx')):
            raise serializers.ValidationError({'detail': 'Unsupported file format. Please upload a CSV or XLSX file.'})
        return value

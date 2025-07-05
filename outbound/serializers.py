from rest_framework import serializers
from .models import Customer, Outbound
from inventory.models import Product

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

    class Meta:
        model = Outbound
        fields = '__all__'
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
                    f"Not enough stock for {product.name}. Available: {product.quantity}, Requested: {quantity}"
                )
        return data

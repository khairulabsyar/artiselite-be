from rest_framework import serializers
from .models import Product


class FileUploadSerializer(serializers.Serializer):
    """
    Serializer for handling file uploads.
    """
    file = serializers.FileField()


class ProductSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        """
        Handles creation of a Product instance, passing audit context to the model.
        The _user and _reason kwargs are injected by the view and passed to save().
        """
        # The save method of the serializer merges kwargs into validated_data.
        # We pop them here to prevent them from being passed to the model constructor.
        user = validated_data.pop('_user', None)
        reason = validated_data.pop('_reason', 'Product created via API.')

        # Create the instance in memory
        product = Product(**validated_data)

        # Call the overridden save method on the model instance, which should handle logging.
        # This assumes Product.save() is customized to accept these kwargs.
        product.save(_user=user, _reason=reason)

        return product

    def update(self, instance, validated_data):
        """
        Handles updates to a Product instance, passing audit context to the model.
        """
        user = validated_data.pop('_user', None)
        reason = validated_data.pop('_reason', 'Product updated via API.')

        # Update instance attributes from validated_data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Call the overridden save method with audit context
        instance.save(_user=user, _reason=reason)
        return instance

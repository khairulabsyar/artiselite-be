from rest_framework import serializers

from .models import Attachment


class AttachmentSerializer(serializers.ModelSerializer):
    """Serializer for the Attachment model."""
    class Meta:
        model = Attachment
        fields = ['id', 'file', 'original_filename', 'created_at']
        read_only_fields = ['original_filename', 'created_at']

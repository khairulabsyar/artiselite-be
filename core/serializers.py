from rest_framework import serializers

from .models import Attachment
from auditlog.models import LogEntry
from users.serializers import UserSerializer


class AttachmentSerializer(serializers.ModelSerializer):
    """Serializer for the Attachment model."""
    class Meta:
        model = Attachment
        fields = ['id', 'file', 'original_filename', 'created_at']
        read_only_fields = ['original_filename', 'created_at']


class LogEntrySerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)

    class Meta:
        model = LogEntry
        fields = ['id', 'actor', 'action', 'timestamp', 'object_repr', 'changes_dict']

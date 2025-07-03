import os
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

def get_upload_path(instance, filename):
    """Generates a unique upload path for attachments."""
    return os.path.join(
        f'attachments/{instance.content_type.model}/{instance.object_id}', filename
    )

class Attachment(models.Model):
    """Represents a file attached to any other model instance."""
    file = models.FileField(upload_to=get_upload_path)
    original_filename = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    # Generic relation to link to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return self.original_filename

    def save(self, *args, **kwargs):
        if not self.pk:  # If the object is new
            self.original_filename = self.file.name
        super().save(*args, **kwargs)

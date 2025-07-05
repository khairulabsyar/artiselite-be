from django.contrib import admin

from .models import Attachment


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'content_type', 'object_id', 'created_at')
    list_filter = ('content_type',)
    search_fields = ('original_filename',)

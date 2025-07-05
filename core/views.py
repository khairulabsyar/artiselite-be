from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers, status, viewsets
from rest_framework.response import Response

from .models import Attachment
from .serializers import AttachmentSerializer


class AttachmentViewSet(viewsets.ModelViewSet):
    """API endpoint for managing attachments."""
    queryset = Attachment.objects.all()
    serializer_class = AttachmentSerializer

    def get_queryset(self):
        """
        Optionally restricts the returned attachments to a given object,
        by filtering against `content_type` (ID) and `object_id` query parameters.
        """
        queryset = super().get_queryset()
        content_type_id = self.request.query_params.get('content_type')
        object_id = self.request.query_params.get('object_id')

        if content_type_id and object_id:
            queryset = queryset.filter(content_type_id=content_type_id, object_id=object_id)
        
        return queryset

    def create(self, request, *args, **kwargs):
        """
        Handles file uploads and associates them with a parent object.
        Expects 'file', 'content_type' (ID), and 'object_id' in the multipart request.
        """
        file_serializer = self.get_serializer(data=request.data)
        file_serializer.is_valid(raise_exception=True)
        
        content_type_id = request.data.get('content_type')
        object_id = request.data.get('object_id')

        if not content_type_id or not object_id:
            raise serializers.ValidationError(
                {'detail': "'content_type' (ID) and 'object_id' are required."}
            )

        try:
            # Verify that the content type and object exist
            content_type = ContentType.objects.get_for_id(content_type_id)
            model_class = content_type.model_class()
            model_class.objects.get(pk=object_id)
        except ContentType.DoesNotExist:
            raise serializers.ValidationError({'detail': "Invalid 'content_type' ID."})
        except model_class.DoesNotExist:
            raise serializers.ValidationError({'detail': f"No object found for model {model_class.__name__} with ID {object_id}."})
        except Exception:
             raise serializers.ValidationError({'detail': 'Invalid content_type or object_id.'})

        # Save the attachment with the generic foreign key
        file_serializer.save(content_type=content_type, object_id=object_id)
        
        headers = self.get_success_headers(file_serializer.data)
        return Response(file_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

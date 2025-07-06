import json

import pandas as pd
from django.db import transaction
from django.http import QueryDict
from inventory.models import Product
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from users.permissions import IsAdminUser, AllowOperatorCreateOnly
from core.mixins import AuditLogMixin

from .models import Inbound, InboundItem, Supplier
from .serializers import (
    InboundBulkUploadSerializer,
    InboundSerializer,
    SupplierSerializer,
)


class SupplierViewSet(viewsets.ModelViewSet):
    """API endpoint for managing suppliers."""
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return super().get_permissions()


class InboundViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing inbound shipments.
    Operators can create inbound shipments but cannot update or delete them.
    """
    queryset = Inbound.objects.prefetch_related('items__product').all()
    serializer_class = InboundSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [permissions.IsAuthenticated, AllowOperatorCreateOnly]

    def _prepare_data(self, request):
        """Prepares request data by handling QueryDicts and nested JSON."""
        data = request.data
        # If data is a QueryDict, convert it to a mutable dictionary
        if isinstance(data, QueryDict):
            data = {key: data.get(key) for key in data}

        # If 'items' is a JSON string (common with multipart/form-data), parse it.
        if 'items' in data and isinstance(data.get('items'), str):
            try:
                data['items'] = json.loads(data['items'])
            except json.JSONDecodeError:
                # Let the serializer handle the validation error if it's not valid JSON
                pass

        # For JSON requests from the browsable API, a file field might be sent as an
        # empty string. We should ignore it to allow optional file uploads.
        if request.content_type == 'application/json' and 'uploaded_attachments' in data and isinstance(data.get('uploaded_attachments'), str):
            data.pop('uploaded_attachments')

        return data

    def create(self, request, *args, **kwargs):
        """Handles creation of an inbound shipment, with special handling for multipart data."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Pop attachments before saving, as they are not a model field
        uploaded_attachments = serializer.validated_data.pop('uploaded_attachments', None)

        # This calls the method in AuditLogMixin, which sets the actor
        self.perform_create(serializer)

        # After perform_create, the instance is available on the serializer
        inbound_instance = serializer.instance

        # Handle attachments now that the instance exists
        if uploaded_attachments:
            from core.models import Attachment
            for attachment_file in uploaded_attachments:
                Attachment.objects.create(content_object=inbound_instance, file=attachment_file)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        """Handles updates to an inbound shipment, with special handling for multipart data."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = self._prepare_data(request)
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # Pop attachments before saving
        uploaded_attachments = serializer.validated_data.pop('uploaded_attachments', None)

        # This calls the method in AuditLogMixin, which sets the actor
        self.perform_update(serializer)

        # Handle attachments
        if uploaded_attachments:
            from core.models import Attachment
            for attachment_file in uploaded_attachments:
                Attachment.objects.create(content_object=instance, file=attachment_file)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    @action(detail=False, methods=['post'], serializer_class=InboundBulkUploadSerializer)
    def bulk_upload(self, request):
        """Handles bulk creation of inbound shipments from a CSV or XLSX file."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file = serializer.validated_data['file']

        try:
            df = pd.read_csv(file, dtype={'inbound_ref': str}) if file.name.endswith('.csv') else pd.read_excel(file, dtype={'inbound_ref': str})
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')

            # Validate required columns
            required_cols = {'inbound_ref', 'inbound_date', 'supplier_email', 'product_sku', 'quantity', 'unit_price'}
            if not required_cols.issubset(df.columns):
                missing_cols = required_cols - set(df.columns)
                return Response(
                    {'error': f'Missing required columns: {list(missing_cols)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate and convert date format before processing
            df['parsed_date'] = pd.to_datetime(df['inbound_date'], errors='coerce').dt.date
            
            invalid_dates = df[df['parsed_date'].isna()]
            if not invalid_dates.empty:
                # +2 to account for 0-based index and header row
                error_rows = [i + 2 for i in invalid_dates.index.tolist()]
                return Response(
                    {
                        'error': 'Invalid or ambiguous date format found.',
                        'details': f'Please use a consistent format like YYYY-MM-DD. Check rows: {error_rows}'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            with transaction.atomic():
                # Group by inbound reference to create separate inbound shipments
                for ref, group in df.groupby('inbound_ref'):
                    first_row = group.iloc[0]
                    supplier = Supplier.objects.get(email=first_row['supplier_email'])
                    
                    # Create a new Inbound shipment for each unique reference
                    inbound_shipment = Inbound.objects.create(
                        supplier=supplier,
                        inbound_date=first_row['parsed_date'],
                        status='PENDING',
                        notes=f'Bulk upload ref: {ref}'
                    )

                    for _, row in group.iterrows():
                        product = Product.objects.get(sku=row['product_sku'])
                        InboundItem.objects.create(
                            inbound=inbound_shipment,
                            product=product,
                            quantity=row['quantity'],
                            unit_price=row['unit_price']
                        )

            return Response({'status': 'Bulk upload successful'}, status=status.HTTP_201_CREATED)

        except (Supplier.DoesNotExist, Product.DoesNotExist) as e:
            return Response({'error': f'Invalid data: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'An error occurred: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)



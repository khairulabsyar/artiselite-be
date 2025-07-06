import pandas as pd
from core.models import Attachment
from django.db import transaction
from inventory.models import Product
from rest_framework import permissions, status, viewsets
from users.permissions import IsAdminUser, AllowOperatorCreateOnly
from core.mixins import AuditLogMixin
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Customer, Outbound
from .serializers import (
    CustomerSerializer,
    OutboundBulkUploadSerializer,
    OutboundSerializer,
)


class CustomerViewSet(viewsets.ModelViewSet):
    """API endpoint that allows customers to be viewed or edited."""
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return super().get_permissions()

class OutboundViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing outbound transactions.
    Operators can create outbound records but cannot update or delete them.
    """
    queryset = Outbound.objects.all().order_by('-created_at')
    serializer_class = OutboundSerializer
    permission_classes = [permissions.IsAuthenticated, AllowOperatorCreateOnly]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_attachments = serializer.validated_data.pop('uploaded_attachments', None)

        try:
            self.perform_create(serializer)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        if uploaded_attachments:
            outbound_instance = serializer.instance
            for attachment_file in uploaded_attachments:
                Attachment.objects.create(content_object=outbound_instance, file=attachment_file)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        uploaded_attachments = serializer.validated_data.pop('uploaded_attachments', None)

        try:
            self.perform_update(serializer)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        if uploaded_attachments:
            for attachment_file in uploaded_attachments:
                Attachment.objects.create(content_object=instance, file=attachment_file)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    @action(detail=False, methods=['post'], serializer_class=OutboundBulkUploadSerializer)
    def bulk_upload(self, request):
        """Handles bulk uploading of outbound records from a CSV or XLSX file."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file = serializer.validated_data['file']

        try:
            df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')

            required_cols = {'product_sku', 'customer_email', 'quantity', 'outbound_date'}
            if not required_cols.issubset(df.columns):
                missing_cols = required_cols - set(df.columns)
                return Response(
                    {'error': f'Missing required columns: {list(missing_cols)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            df['parsed_date'] = pd.to_datetime(df['outbound_date'], errors='coerce').dt.date
            invalid_dates = df[df['parsed_date'].isna()]
            if not invalid_dates.empty:
                error_rows = [i + 2 for i in invalid_dates.index.tolist()]
                return Response(
                    {
                        'error': 'Invalid or ambiguous date format found.',
                        'details': f'Please use a consistent format like YYYY-MM-DD. Check rows: {error_rows}'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            outbounds_to_create = []
            errors = []
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        product = Product.objects.get(sku=row['product_sku'])
                        customer = Customer.objects.get(email=row['customer_email'])
                        quantity = int(row['quantity'])

                        if product.quantity < quantity:
                            errors.append(f"Row {index + 2}: Not enough stock for {product.name}. Available: {product.quantity}, Requested: {quantity}")
                            continue

                        outbounds_to_create.append(
                            Outbound(
                                product=product,
                                customer=customer,
                                quantity=quantity,
                                outbound_date=row['parsed_date'],
                                so_ref=row.get('so_ref'),
                                notes=row.get('notes'),
                                created_by=request.user
                            )
                        )
                    except Product.DoesNotExist:
                        errors.append(f"Row {index + 2}: Product with SKU '{row['product_sku']}' not found.")
                    except Customer.DoesNotExist:
                        errors.append(f"Row {index + 2}: Customer with email '{row['customer_email']}' not found.")
                    except ValueError:
                        errors.append(f"Row {index + 2}: Invalid quantity. Must be a whole number.")

                if errors:
                    transaction.set_rollback(True)
                    return Response({'detail': 'Errors found in file', 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

                Outbound.objects.bulk_create(outbounds_to_create)

            return Response({'detail': f'{len(outbounds_to_create)} outbound records created successfully.'}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': f'An error occurred: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
            
    @action(detail=True, methods=['post'])
    def complete_outbound(self, request, pk=None):
        """Mark an outbound record as completed and update inventory.
        
        This action will:
        1. Change the outbound status to COMPLETED
        
        Note: The model's save method automatically handles:
        2. Deducting the quantity from product inventory
        3. Creating an inventory log entry
        """
        outbound = self.get_object()
        
        if outbound.status == 'COMPLETED':
            return Response({'detail': 'Outbound is already completed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if there's enough stock before attempting to complete
        if outbound.product.quantity < outbound.quantity:
            return Response(
                {'detail': f'Not enough stock. Available: {outbound.product.quantity}, Required: {outbound.quantity}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Just update status - the model's save method will handle inventory deduction
        # and log creation via the _deduct_inventory method automatically
        outbound.status = 'COMPLETED'
        outbound.save(_user=request.user, _reason='Completed via API')
            
        return Response({'detail': 'Outbound completed successfully'}, status=status.HTTP_200_OK)


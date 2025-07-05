import pandas as pd
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from django.db import transaction
from .models import Customer, Outbound
from .serializers import CustomerSerializer, OutboundSerializer, OutboundBulkUploadSerializer
from inventory.models import Product, InventoryLog
from core.models import Attachment

class CustomerViewSet(viewsets.ModelViewSet):
    """API endpoint that allows customers to be viewed or edited."""
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

class OutboundViewSet(viewsets.ModelViewSet):
    """API endpoint that allows outbound transactions to be viewed or edited."""
    queryset = Outbound.objects.all()
    serializer_class = OutboundSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        uploaded_attachments = serializer.validated_data.pop('uploaded_attachments', [])
        
        try:
            outbound = serializer.save(created_by=self.request.user)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        for attachment_file in uploaded_attachments:
            Attachment.objects.create(
                file=attachment_file,
                content_object=outbound
            )
        
        headers = self.get_success_headers(serializer.data)
        response_serializer = self.get_serializer(outbound)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        uploaded_attachments = serializer.validated_data.pop('uploaded_attachments', [])

        try:
            self.perform_update(serializer)
        except ValueError as e:
            raise ValidationError({'detail': str(e)})

        for attachment_file in uploaded_attachments:
            Attachment.objects.create(
                file=attachment_file,
                content_object=instance
            )

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        
        response_serializer = self.get_serializer(instance)
        return Response(response_serializer.data)

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

    @action(detail=True, methods=['post'], url_path='complete')
    def complete_outbound(self, request, pk=None):
        """Marks an outbound transaction as completed and deducts the stock."""
        outbound = self.get_object()

        if outbound.status == 'COMPLETED':
            return Response({'detail': 'Outbound is already completed.'}, status=status.HTTP_400_BAD_REQUEST)

        if outbound.status == 'CANCELLED':
            return Response({'detail': 'Cannot complete a cancelled outbound.'}, status=status.HTTP_400_BAD_REQUEST)

        product = outbound.product
        if product.quantity < outbound.quantity:
            return Response(
                {'detail': f'Not enough stock for {product.name}. Available: {product.quantity}, Requested: {outbound.quantity}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                # Re-fetch and lock the product row to prevent race conditions
                product_to_update = Product.objects.select_for_update().get(pk=product.pk)

                # Check stock again with the lock in place
                if product_to_update.quantity < outbound.quantity:
                    return Response(
                        {'detail': f'Stock level changed. Not enough stock for {product.name}. Available: {product_to_update.quantity}, Requested: {outbound.quantity}'},
                        status=status.HTTP_409_CONFLICT
                    )

                # Deduct product quantity atomically using F() expression
                product_to_update.quantity -= outbound.quantity
                product_to_update.save()

                # Update outbound status
                outbound.status = 'COMPLETED'
                outbound.save()

                # Refresh the product object to get the actual new quantity
                product_to_update.refresh_from_db()

                # Create an inventory log entry
                InventoryLog.objects.create(
                    product=product_to_update,
                    user=request.user,
                    quantity_change=-outbound.quantity,
                    new_quantity=product_to_update.quantity,
                    reason=f"Outbound transaction for SO: {outbound.so_ref or 'N/A'}"
                )

            return Response(self.get_serializer(outbound).data)
        except Exception as e:
            return Response({'detail': f'An unexpected error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

import pandas as pd
from django.db import transaction, IntegrityError
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import serializers
from django.db.models import F
from .models import Product, InventoryLog
from .serializers import ProductSerializer, FileUploadSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('-updated_at')
    serializer_class = ProductSerializer

    def get_queryset(self):
        """
        Override to handle custom filtering and searching.
        """
        queryset = super().get_queryset()

        # Handle category filtering
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        # Handle archival filtering
        is_archived = self.request.query_params.get('is_archived')
        if is_archived is not None:
            archived_bool = is_archived.lower() in ['true', '1']
            queryset = queryset.filter(is_archived=archived_bool)

        # Handle searching
        search_term = self.request.query_params.get('search')
        if search_term:
            queryset = queryset.filter(
                Q(name__icontains=search_term) |
                Q(sku__icontains=search_term) |
                Q(category__icontains=search_term) |
                Q(tags__icontains=search_term)
            )

        return queryset

    def get_serializer_class(self):
        """
        Return the appropriate serializer class based on the action.
        For bulk_upload, use the FileUploadSerializer.
        """
        if self.action == 'bulk_upload':
            return FileUploadSerializer
        return ProductSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        reason = serializer.validated_data.pop('reason', 'Creation via API')
        try:
            serializer.save(_user=user, _reason=reason)
        except IntegrityError as e:
            raise ValidationError({'detail': 'Failed to create product. This may be due to a duplicate SKU or invalid data.'})
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        reason = serializer.validated_data.pop('reason', 'Update via API')
        try:
            serializer.save(_user=user, _reason=reason)
        except IntegrityError as e:
            raise ValidationError({'detail': 'Update failed. Quantity cannot be negative.'})

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        return Response(serializer.data)

    @action(
        detail=False, 
        methods=['post'], 
        url_path='bulk-upload',
        parser_classes=[MultiPartParser, FormParser]
    )
    def bulk_upload(self, request):
        """
        An endpoint to bulk create or update products from a CSV or XLSX file.
        'sku' is used as the unique identifier for updates.
        Required columns: 'sku', 'name'.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file_obj = serializer.validated_data['file']

        try:
            if file_obj.name.endswith('.csv'):
                df = pd.read_csv(file_obj)
            elif file_obj.name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file_obj)
            else:
                return Response({'error': 'Unsupported file format. Use CSV or XLSX.'}, status=status.HTTP_400_BAD_REQUEST)

            required_columns = {'sku', 'name'}
            if not required_columns.issubset(df.columns):
                return Response({
                    'error': f'Missing required columns. Required: {list(required_columns)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Replace NaN with None for database compatibility
            df = df.where(pd.notnull(df), None)
            
            created_count = 0
            updated_count = 0

            with transaction.atomic():
                for index, row in df.iterrows():
                    sku = row.get('sku')
                    if not sku:
                        continue

                    product_data = row.to_dict()
                    product_data = {k: v for k, v in product_data.items() if pd.notna(v)}
                    user = request.user if request.user.is_authenticated else None

                    if 'quantity' in product_data:
                        product_data['quantity'] = int(product_data['quantity'])

                    instance = Product.objects.filter(sku=sku).first()

                    if instance:
                        serializer = ProductSerializer(instance, data=product_data, partial=True)
                        reason = "Bulk upload: Updated"
                    else:
                        serializer = ProductSerializer(data=product_data)
                        reason = "Bulk upload: Created"

                    if serializer.is_valid():
                        serializer.save(_user=user, _reason=reason)
                        if instance:
                            updated_count += 1
                        else:
                            created_count += 1
                    else:
                        # If any row is invalid, fail the entire transaction and report the error.
                        raise serializers.ValidationError({
                            'detail': 'Row validation failed.',
                            'row_index': index + 2,  # +2 for header and 0-indexing
                            'errors': serializer.errors
                        })
            
            return Response({
                'status': 'Bulk upload successful',
                'created': created_count,
                'updated': updated_count
            }, status=status.HTTP_201_CREATED)

        except serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'error': f'An error occurred: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """
        An endpoint to list all products that are at or below their low stock threshold.
        """
        low_stock_products = self.get_queryset().filter(
            quantity__lte=F('low_stock_threshold'),
            is_archived=False
        )
        serializer = ProductSerializer(low_stock_products, many=True)
        return Response(serializer.data)

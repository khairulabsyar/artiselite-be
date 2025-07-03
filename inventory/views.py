import pandas as pd
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.db.models import F
from .models import Product, InventoryLog
from .serializers import ProductSerializer, FileUploadSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('-updated_at')
    serializer_class = ProductSerializer
    search_fields = ['name', 'sku', 'category', 'tags']
    filterset_fields = ['category', 'is_archived']

    def get_serializer_class(self):
        """
        Return the appropriate serializer class based on the action.
        For bulk_upload, use the FileUploadSerializer.
        """
        if self.action == 'bulk_upload':
            return FileUploadSerializer
        return ProductSerializer

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        reason = serializer.validated_data.pop('reason', 'Creation via API')
        serializer.save(_user=user, _reason=reason)

    def perform_update(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        reason = serializer.validated_data.pop('reason', 'Update via API')
        serializer.save(_user=user, _reason=reason)

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
                for _, row in df.iterrows():
                    sku = row.get('sku')
                    if not sku:
                        continue

                    product_data = row.to_dict()
                    product_data = {k: v for k, v in product_data.items() if pd.notna(v)}

                    try:
                        product = Product.objects.get(sku=sku)
                        created = False
                    except Product.DoesNotExist:
                        product = Product(sku=sku)
                        created = True

                    for key, value in product_data.items():
                        setattr(product, key, value)

                    # Manually set context for logging
                    product._user = request.user if request.user.is_authenticated else None
                    product._reason = f"Bulk upload: {'Created' if created else 'Updated'}"
                    
                    product.save() # This will now correctly trigger the logging

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

            return Response({
                'status': 'Bulk upload successful',
                'created': created_count,
                'updated': updated_count
            }, status=status.HTTP_201_CREATED)

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

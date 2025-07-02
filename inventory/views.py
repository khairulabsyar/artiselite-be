import pandas as pd
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.db.models import F
from .models import Product, InventoryLog
from .serializers import ProductSerializer

class ProductViewSet(viewsets.ModelViewSet):
    parser_classes = (MultiPartParser, FormParser)

    def perform_create(self, serializer):
        """
        Custom create logic to pass user and reason to the model's save method.
        """
        user = self.request.user if self.request.user.is_authenticated else None
        reason = serializer.validated_data.get('reason', 'Creation via API')
        serializer.save(_user=user, _reason=reason)

    def perform_update(self, serializer):
        """
        Custom update logic to pass user and reason to the model's save method.
        """
        user = self.request.user if self.request.user.is_authenticated else None
        reason = serializer.validated_data.get('reason', 'Update via API')
        serializer.save(_user=user, _reason=reason)

    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        """
        An endpoint to bulk create or update products from a CSV or XLSX file.
        The file should contain columns matching the Product model fields.
        'sku' is used as the unique identifier for updates.
        Required columns: 'sku', 'name'.
        Optional columns: 'tags', 'description', 'category', 'quantity', 'low_stock_threshold'.
        """
        file_obj = request.data.get('file', None)
        if not file_obj:
            return Response({'error': 'File not provided.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if file_obj.name.endswith('.csv'):
                df = pd.read_csv(file_obj)
            elif file_obj.name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file_obj)
            else:
                return Response({'error': 'Unsupported file format. Use CSV or XLSX.'}, status=status.HTTP_400_BAD_REQUEST)

            df = df.where(pd.notnull(df), None)
            required_columns = {'sku', 'name'}
            if not required_columns.issubset(df.columns):
                return Response({'error': f'Missing required columns: {required_columns - set(df.columns)}'}, status=status.HTTP_400_BAD_REQUEST)

            created_count = 0
            updated_count = 0

            with transaction.atomic():
                for _, row in df.iterrows():
                    sku = row.get('sku')
                    if not sku:
                        continue

                    product, created = Product.objects.get_or_create(sku=sku, defaults={'name': row.get('name')})

                    product.name = row.get('name', product.name)
                    product.tags = row.get('tags', product.tags)
                    product.description = row.get('description', product.description)
                    product.category = row.get('category', product.category)
                    product.quantity = int(row.get('quantity', product.quantity))
                    product.low_stock_threshold = int(row.get('low_stock_threshold', product.low_stock_threshold))
                    
                    # Pass context for logging
                    product._user = request.user if request.user.is_authenticated else None
                    product._reason = f"Bulk upload: {'Created' if created else 'Updated'}"
                    
                    product.save()

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

            return Response({
                'message': 'Bulk upload successful.',
                'products_created': created_count,
                'products_updated': updated_count
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': f'An error occurred: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """
        An endpoint to retrieve all products that are at or below their
        low stock threshold.
        """
        low_stock_products = self.get_queryset().filter(
            quantity__lte=F('low_stock_threshold'),
            is_archived=False
        )
        serializer = self.get_serializer(low_stock_products, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    """
    API endpoint that allows products to be viewed or edited.
    Provides `list`, `create`, `retrieve`, `update`, and `destroy` actions.
    """
    queryset = Product.objects.all().order_by('-updated_at')
    serializer_class = ProductSerializer
    search_fields = ['name', 'sku', 'category', 'tags']
    filterset_fields = ['category', 'is_archived']


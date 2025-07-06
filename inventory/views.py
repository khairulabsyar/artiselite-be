import pandas as pd
from django.db import transaction
from django.db.models import F, Q
from rest_framework.exceptions import ValidationError
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from auditlog.context import set_actor

from users.permissions import AllowOperatorCreateOnly
from core.mixins import AuditLogMixin
from .models import Product
from .serializers import ProductSerializer, FileUploadSerializer


class ProductViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing products.
    Operators can create products but cannot update or delete them.
    """
    queryset = Product.objects.all().order_by('-updated_at')
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, AllowOperatorCreateOnly]

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

    def perform_create(self, serializer):
        """
        Sets the actor using the mixin and saves the new product instance,
        passing the user and a reason to the serializer.
        """
        user = self.request.user if self.request.user.is_authenticated else None
        
        # Get reason from request data if provided, otherwise use default
        if 'reason' in self.request.data:
            reason = self.request.data['reason']
        else:
            reason = "Product created via API"
            
        # Don't pass parameters to super, as AuditLogMixin.perform_create doesn't accept them
        # Instead, directly modify the serializer.save call like the mixin does
        with set_actor(user):
            serializer.save(_user=user, _reason=reason)

    def perform_update(self, serializer):
        """
        Sets the actor using the mixin and saves the updated product instance,
        passing the user and a reason to the serializer.
        """
        user = self.request.user if self.request.user.is_authenticated else None
        
        # Get reason from request data if provided, otherwise use default
        if 'reason' in self.request.data:
            reason = self.request.data['reason']
        else:
            reason = "Product updated via API"
            
        # Don't pass parameters to super, as AuditLogMixin.perform_update doesn't accept them
        # Instead, directly modify the serializer.save call like the mixin does
        with set_actor(user):
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
                        raise ValidationError({
                            'detail': 'Row validation failed.',
                            'row_index': index + 2,
                            'errors': serializer.errors
                        })
            
            return Response({
                'status': 'Bulk upload successful',
                'created': created_count,
                'updated': updated_count
            }, status=status.HTTP_201_CREATED)

        except ValidationError as e:
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

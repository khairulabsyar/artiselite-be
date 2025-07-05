from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from .models import Customer, Outbound
from .serializers import CustomerSerializer, OutboundSerializer
from inventory.models import Product, InventoryLog

class CustomerViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows customers to be viewed or edited.
    """
    queryset = Customer.objects.all().order_by('-created_at')
    serializer_class = CustomerSerializer

class OutboundViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows outbound transactions to be viewed or edited.
    """
    queryset = Outbound.objects.all().order_by('-outbound_date')
    serializer_class = OutboundSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete_outbound(self, request, pk=None):
        """
        Marks an outbound transaction as completed and deducts the stock.
        """
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
                # Deduct product quantity
                product.quantity -= outbound.quantity
                product.save()

                # Update outbound status
                outbound.status = 'COMPLETED'
                outbound.save()

                # Create an inventory log entry
                InventoryLog.objects.create(
                    product=product,
                    transaction_type='OUTBOUND',
                    quantity_change=-outbound.quantity,
                    related_object=outbound
                )

            return Response(self.get_serializer(outbound).data)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

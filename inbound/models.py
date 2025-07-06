from core.models import Attachment
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models, transaction
from auditlog.registry import auditlog
from django.db.models import F
from inventory.models import InventoryLog, Product


class Supplier(models.Model):
    """Represents a supplier of products."""
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Inbound(models.Model):
    """Represents an inbound shipment from a supplier."""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='inbounds')
    inbound_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    attachments = GenericRelation(Attachment, related_query_name='inbound')

    def __str__(self):
        return f"Inbound {self.id} from {self.supplier.name} on {self.inbound_date}"

    def save(self, _user=None, _reason=None, *args, **kwargs):
        """
        Custom save method to update inventory when an inbound shipment's status
        is changed to 'COMPLETED'.
        """
        # Keep track of the status before saving and the user context
        old_status = None
        if self.pk:
            try:
                old_status = Inbound.objects.get(pk=self.pk).status
            except Inbound.DoesNotExist:
                pass
        
        # Attach user to instance for use in post-save logic
        self._user = _user

        super().save(*args, **kwargs)  # Save the object first

        if old_status != 'COMPLETED' and self.status == 'COMPLETED':
        
            try:
                with transaction.atomic():
                    user = self._user

                    if not self.items.all().exists():
                    
                        return

                    for item in self.items.all():
                        product = item.product
                    

                        Product.objects.filter(pk=product.pk).update(quantity=F('quantity') + item.quantity)
                    

                        product.refresh_from_db()
                    

                        InventoryLog.objects.create(
                            product=product,
                            user=user,
                            quantity_change=item.quantity,
                            new_quantity=product.quantity,
                            reason=_reason or f'Inbound shipment #{self.id} completed.'
                        )
                    
            
            except Exception:
            
                # Handle the error, maybe revert the status or log it for manual intervention
                self.status = old_status
                super().save(update_fields=['status'])

class InboundItem(models.Model):
    """Represents a single product within an inbound shipment."""
    inbound = models.ForeignKey(Inbound, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='inbound_items')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per unit at the time of purchase")

    class Meta:
        unique_together = ('inbound', 'product')

    def __str__(self):
        return f"{self.quantity} x {self.product.name} for Inbound {self.inbound.id}"

auditlog.register(Supplier)
auditlog.register(Inbound)
auditlog.register(InboundItem)

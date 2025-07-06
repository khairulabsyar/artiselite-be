from core.models import Attachment
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from auditlog.registry import auditlog
from inventory.models import Product, InventoryLog


class Customer(models.Model):
    """
    Represents a customer who receives products from the warehouse.
    """
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Outbound(models.Model):
    """
    Represents an outbound transaction, when a product is dispatched from the warehouse.
    """
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='outbounds')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='outbounds')
    quantity = models.PositiveIntegerField()
    so_ref = models.CharField(max_length=255, blank=True, null=True)
    outbound_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='outbound_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    attachments = GenericRelation(Attachment)

    def __str__(self):
        return f'Outbound #{self.id} - {self.product.name} to {self.customer.name}'

    def save(self, *args, **kwargs):
        # Pop custom kwargs before calling super().save()
        _user = kwargs.pop('_user', None)
        _reason = kwargs.pop('_reason', None)

        # Store the original status to detect changes
        is_new = self._state.adding
        if not is_new:
            old_instance = Outbound.objects.get(pk=self.pk)
            old_status = old_instance.status
        else:
            old_status = None

        # If created_by is not set, use the _user from kwargs
        if is_new and not self.created_by and _user:
            self.created_by = _user

        # Check if status is changing to COMPLETED
        status_changing_to_completed = False
        if not is_new and self.status == 'COMPLETED' and old_status != 'COMPLETED':
            status_changing_to_completed = True
            
        # Call parent save method
        super().save(*args, **kwargs)

        # Handle inventory deduction separately, after the main save
        if status_changing_to_completed:
            self._deduct_inventory(_user, _reason)
            
    def _deduct_inventory(self, user, reason):
        """Handle inventory deduction and logging when an outbound is completed."""
        from django.db import transaction
        
        try:
            with transaction.atomic():
                # Get the latest version of the product with a lock
                product = Product.objects.select_for_update().get(pk=self.product.pk)
                
                # Check if we have enough stock
                if product.quantity < self.quantity:
                    raise ValueError(f"Not enough stock for {product.name}. Available: {product.quantity}, Requested: {self.quantity}")
                
                # Update the quantity directly in the database
                Product.objects.filter(pk=product.pk).update(
                    quantity=models.F('quantity') - self.quantity
                )
                
                # Get the updated product
                updated_product = Product.objects.get(pk=product.pk)
                
                # Create the inventory log
                InventoryLog.objects.create(
                    product=updated_product,
                    quantity_change=-self.quantity,
                    new_quantity=updated_product.quantity,
                    user=user,
                    reason=f"Outbound #{self.id} completed. {reason or ''}".strip()
                )
                
                return True
        except Exception:
            # Simply re-raise any exceptions that occur
            raise



auditlog.register(Customer)
auditlog.register(Outbound)

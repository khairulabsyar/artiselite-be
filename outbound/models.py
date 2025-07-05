from django.db import models, transaction, IntegrityError
from django.db.models import F
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericRelation
from inventory.models import Product, InventoryLog
from core.models import Attachment

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
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='outbound_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    attachments = GenericRelation(Attachment)

    def __str__(self):
        return f'Outbound #{self.id} - {self.product.name} to {self.customer.name}'

    def save(self, *args, **kwargs):
        """
        Custom save method to update inventory when an outbound shipment's status
        is changed to 'COMPLETED'.
        """
        old_status = None
        if self.pk:
            try:
                old_status = Outbound.objects.get(pk=self.pk).status
            except Outbound.DoesNotExist:
                pass

        super().save(*args, **kwargs)  # Save the object first

        if old_status != 'COMPLETED' and self.status == 'COMPLETED':
            try:
                with transaction.atomic():
                    # Get user from instance if attached (e.g., from admin), otherwise use creator
                    user = getattr(self, '_user', self.created_by)

                    product = self.product
                    
                    if product.quantity < self.quantity:
                        raise ValueError(f"Not enough stock for {product.name}. Available: {product.quantity}, Requested: {self.quantity}")

                    # Deduct stock atomically
                    Product.objects.filter(pk=product.pk).update(quantity=F('quantity') - self.quantity)
                    
                    product.refresh_from_db()
                    
                    InventoryLog.objects.create(
                        product=product,
                        user=user,
                        quantity_change=-self.quantity,  # Negative for outbound
                        new_quantity=product.quantity,
                        reason=f'Outbound shipment #{self.id} completed.'
                    )
            
            except (ValueError, IntegrityError) as e:
                # If any error occurs (e.g., stock issue), revert the status change
                self.status = old_status
                super().save(update_fields=['status'])
                # Re-raise a clean exception for the view to catch and handle
                raise ValueError("Insufficient stock to complete this order.") from e

from django.conf import settings
from django.db import models
from auditlog.registry import auditlog
from django.db.models import Q


class Product(models.Model):
    """
    Represents a product in the warehouse inventory.
    """
    name = models.CharField(max_length=255, help_text="The name of the product.")
    sku = models.CharField(max_length=100, unique=True, help_text="Stock Keeping Unit, must be unique.")
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated tags for easy filtering.")
    description = models.TextField(blank=True, help_text="A detailed description of the product.")
    category = models.CharField(max_length=100, blank=True, help_text="Product category.")
    quantity = models.PositiveIntegerField(default=0, help_text="Current quantity in stock.")
    low_stock_threshold = models.PositiveIntegerField(default=10, help_text="Threshold for low stock alerts.")
    is_archived = models.BooleanField(default=False, help_text="Whether the product is archived and not in active use.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def save(self, *args, **kwargs):
        """
        Custom save method to log inventory changes automatically.
        Accepts `_user` and `_reason` kwargs for audit purposes.
        """

        # Pop custom kwargs before they reach the super().save() method
        user = kwargs.pop('_user', None)
        reason = kwargs.pop('_reason', 'No reason provided')

        # Check if the instance is new or if the quantity has changed
        is_new = self._state.adding
        old_quantity = 0
        if not is_new:
            try:
                old_quantity = Product.objects.get(pk=self.pk).quantity
            except Product.DoesNotExist:
                # This case should ideally not happen if the instance exists
                pass

        super().save(*args, **kwargs)  # Save the product instance first

        quantity_changed = is_new or self.quantity != old_quantity

        if quantity_changed:
            InventoryLog.objects.create(
                product=self,
                user=user,
                quantity_change=self.quantity - old_quantity,
                new_quantity=self.quantity,
                reason=reason
            )

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Products"
        constraints = [
            models.CheckConstraint(check=Q(quantity__gte=0), name='quantity_non_negative')
        ]


class InventoryLog(models.Model):
    """
    Records every change in product quantity for audit purposes.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='logs')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="The user who performed the action."
    )
    quantity_change = models.IntegerField(help_text="The change in quantity. Positive for inbound, negative for outbound.")
    new_quantity = models.PositiveIntegerField(help_text="The new total quantity after the change.")
    reason = models.CharField(max_length=255, blank=True, help_text="The reason for the stock change (e.g., 'Inbound Shipment', 'Sales Order', 'Manual Correction').")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log for {self.product.name} at {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Inventory Logs"


auditlog.register(Product)
auditlog.register(InventoryLog)


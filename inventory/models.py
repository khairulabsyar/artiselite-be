from django.db import models
from django.conf import settings

class Product(models.Model):
    _original_quantity = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_quantity = self.quantity

    def save(self, *args, **kwargs):
        """
        Override the save method to automatically log inventory changes.
        """
        is_new = self._state.adding
        super().save(*args, **kwargs) # Save the object first to get a PK

        # Use a flag to pass the user and reason from the view/admin
        user = getattr(self, '_user', None)
        reason = getattr(self, '_reason', 'Initial stock' if is_new else 'Manual update')

        if self.quantity != self._original_quantity or is_new:
            InventoryLog.objects.create(
                product=self,
                user=user,
                quantity_change=self.quantity - (self._original_quantity or 0),
                new_quantity=self.quantity,
                reason=reason
            )
        self._original_quantity = self.quantity

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

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Products"


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


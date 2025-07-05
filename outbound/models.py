from django.db import models
from django.contrib.auth.models import User
from inventory.models import Product

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
    outbound_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='outbound_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Outbound #{self.id} - {self.product.name} to {self.customer.name}'

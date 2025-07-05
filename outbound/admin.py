from django.contrib import admin
from .models import Customer, Outbound

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'created_at')
    search_fields = ('name', 'email')

@admin.register(Outbound)
class OutboundAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'product', 'quantity', 'status', 'outbound_date')
    list_filter = ('status', 'outbound_date')
    search_fields = ('customer__name', 'product__name')
    autocomplete_fields = ('customer', 'product')

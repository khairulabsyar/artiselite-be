from django.contrib import admin

from .models import Customer, Outbound


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Admin configuration for the Customer model."""
    list_display = ('id', 'name', 'contact_person', 'email', 'phone', 'created_at')
    search_fields = ('name', 'email')

@admin.register(Outbound)
class OutboundAdmin(admin.ModelAdmin):
    """Admin configuration for the Outbound model."""
    list_display = ('id', 'customer', 'product', 'quantity', 'so_ref', 'status', 'outbound_date')
    list_filter = ('status', 'outbound_date')
    search_fields = ('customer__name', 'product__name', 'so_ref')
    autocomplete_fields = ('customer', 'product')

    def save_model(self, request, obj, form, change):
        """Attach the user to the object before saving for audit logging."""
        obj._user = request.user
        super().save_model(request, obj, form, change)

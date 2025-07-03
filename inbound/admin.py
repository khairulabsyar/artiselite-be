from django.contrib import admin
from .models import Supplier, Inbound, InboundItem

class InboundItemInline(admin.TabularInline):
    """
    Allows editing InboundItem records directly within the Inbound admin page.
    """
    model = InboundItem
    extra = 1  # Show one empty form for adding a new item

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Supplier model.
    """
    list_display = ('id', 'name', 'contact_person', 'email', 'phone', 'created_at')
    search_fields = ('name', 'email', 'contact_person')

@admin.register(Inbound)
class InboundAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Inbound model.
    """
    list_display = ('id', 'supplier', 'status', 'created_at')
    list_filter = ('status', 'supplier')
    search_fields = ('id', 'supplier__name')
    autocomplete_fields = ['supplier']  # Provides a search-as-you-type input for suppliers
    inlines = [InboundItemInline]

    def save_model(self, request, obj, form, change):
        """
        Override to attach the user to the object before saving, so the model's
        save method can log who made the change.
        """
        # Attach user to the object for the model's save method
        obj._user = request.user
        super().save_model(request, obj, form, change)

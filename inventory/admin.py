from django.contrib import admin
from .models import Product, InventoryLog

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        """
        Pass the user to the model's save method for logging.
        """
        obj._user = request.user
        super().save_model(request, obj, form, change)

    list_display = ('id', 'name', 'sku', 'tags', 'category', 'quantity', 'low_stock_threshold', 'is_archived', 'updated_at')
    search_fields = ('id', 'name', 'sku', 'category', 'tags')
    list_filter = ('is_archived', 'category', 'created_at')
    ordering = ('-updated_at',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'sku', 'description')
        }),
        ('Categorization', {
            'fields': ('category', 'tags')
        }),
        ('Stock Management', {
            'fields': ('quantity', 'low_stock_threshold', 'is_archived')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(InventoryLog)
class InventoryLogAdmin(admin.ModelAdmin):
    """
    Admin view for the InventoryLog model.
    This should be a read-only view as logs should be immutable.
    """
    list_display = ('product', 'quantity_change', 'new_quantity', 'reason', 'user', 'timestamp')
    list_filter = ('product', 'user', 'timestamp')
    search_fields = ('product__name', 'product__sku', 'reason')
    readonly_fields = [field.name for field in InventoryLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


from django.contrib import admin
from .models import User, Role, Permission, RolePermission, ActivityLog

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Admin configuration for the User model."""
    list_display = ('username', 'email', 'role')
    search_fields = ('username', 'email')

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin configuration for the Role model."""
    list_display = ('name', 'description')

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """Admin configuration for the Permission model."""
    list_display = ('module', 'action', 'description')
    list_filter = ('module', 'action')

@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """Admin configuration for the RolePermission model."""
    list_display = ('role', 'permission')

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Admin configuration for the ActivityLog model."""
    list_display = ('user', 'action', 'model_name', 'record_id', 'timestamp')
    list_filter = ('model_name', 'action')
    search_fields = ('user__username', 'model_name')

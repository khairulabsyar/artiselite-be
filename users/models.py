from django.db import models
from auditlog.registry import auditlog
from django.contrib.auth.models import AbstractUser

class Role(models.Model):
    ADMIN = 'Admin'
    MANAGER = 'Manager'
    OPERATOR = 'Operator'
    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (MANAGER, 'Manager'),
        (OPERATOR, 'Operator'),
    ]
    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Permission(models.Model):
    MODULE_CHOICES = [
        ('INVENTORY', 'Inventory'),
        ('INBOUND', 'Inbound'),
        ('OUTBOUND', 'Outbound'),
        ('USER', 'User Management'),
    ]
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('READ', 'Read'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
    ]
    
    module = models.CharField(max_length=20, choices=MODULE_CHOICES)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ('module', 'action')
    
    def __str__(self):
        return f"{self.get_action_display()} {self.get_module_display()}"

class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('role', 'permission')

class User(AbstractUser):
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    
    def has_permission(self, module, action):
        if not self.role:
            return False
        return self.role.permissions.filter(
            permission__module=module,
            permission__action=action
        ).exists()

class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    record_id = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.user} {self.action} {self.model_name} ({self.record_id}) at {self.timestamp}"


auditlog.register(User)
auditlog.register(Role)

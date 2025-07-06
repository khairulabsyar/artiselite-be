from rest_framework.permissions import BasePermission
from .models import Role

class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
                return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_superuser or (request.user.role and request.user.role.name == Role.ADMIN))
        )


class IsAdminOrManagerUser(BasePermission):
    """
    Allows access only to admin or manager users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_superuser or (request.user.role and request.user.role.name in [Role.ADMIN, Role.MANAGER]))
        )


class AllowOperatorCreateOnly(BasePermission):
    """
    Allows all authenticated users (including Operators) to create records,
    but restricts update/delete operations to Admin and Manager users only.
    """
    def has_permission(self, request, view):
        # All authenticated users can list and retrieve
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user and request.user.is_authenticated
        
        # For create operations, allow all authenticated users
        if request.method == 'POST':
            return request.user and request.user.is_authenticated
        
        # For update/delete operations, restrict to admin/manager
        if request.method in ['PUT', 'PATCH', 'DELETE']:
            return bool(
                request.user and
                request.user.is_authenticated and
                (request.user.is_superuser or (request.user.role and request.user.role.name in [Role.ADMIN, Role.MANAGER]))
            )
        
        return False

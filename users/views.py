from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, BasePermission
from .models import User, Role, Permission
from .serializers import UserRegistrationSerializer, UserSerializer, RoleSerializer, RolePermissionSerializer
from .permissions import IsAdminUser

class UserRegistrationView(APIView):
    """API endpoint for user registration."""
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IsOwner(BasePermission):
    """
    Custom permission to only allow owners of an object to view or edit it.
    """
    def has_object_permission(self, request, view, obj):
        return obj == request.user


class UserViewSet(viewsets.ModelViewSet):
    """API endpoint for managing user accounts."""
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        """Instantiates and returns the list of permissions that this view requires."""
        if self.action == 'me':
            permission_classes = [IsAuthenticated]
        elif self.action in ['retrieve', 'update', 'partial_update']:
            permission_classes = [IsAdminUser | IsOwner]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'], url_path='me', url_name='user-me')
    def me(self, request):
        """Return the authenticated user's data."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class RoleViewSet(viewsets.ModelViewSet):
    """API endpoint for managing user roles."""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdminUser]


class RolePermissionView(APIView):
    """API endpoint for assigning multiple permissions to a role."""
    permission_classes = [IsAdminUser]

    def post(self, request, role_id):
        try:
            role = Role.objects.get(pk=role_id)
        except Role.DoesNotExist:
            return Response({"error": "Role not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RolePermissionSerializer(data=request.data)
        if serializer.is_valid():
            permission_ids = serializer.validated_data['permission_ids']
            permissions = Permission.objects.filter(id__in=permission_ids)
            role.permissions.set(permissions)
            return Response({"message": f"Permissions for role '{role.name}' updated successfully."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

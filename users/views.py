from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from .models import User, Role, Permission
from .serializers import UserRegistrationSerializer, UserSerializer, RoleSerializer, RolePermissionSerializer
from .permissions import IsAdminUser

class UserRegistrationView(APIView):
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdminUser]


class RolePermissionView(APIView):
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

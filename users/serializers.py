from rest_framework import serializers
from .models import User, Role, Permission

class UserRegistrationSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(style={'input_type': 'password'}, write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def save(self):
        user = User(
            email=self.validated_data['email'],
            username=self.validated_data['username']
        )
        password = self.validated_data['password']
        password2 = self.validated_data['password2']
        if password != password2:
            raise serializers.ValidationError({'password': 'Passwords must match.'})
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined']
        read_only_fields = ['date_joined']


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'


class RolePermissionSerializer(serializers.Serializer):
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True
    )

    def validate_permission_ids(self, value):
        """
        Check that all permission_ids exist.
        """
        if not Permission.objects.filter(id__in=value).count() == len(value):
            raise serializers.ValidationError("One or more permissions do not exist.")
        return value

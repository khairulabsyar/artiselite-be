"""
URL configuration for artiselite_be project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import ViewSets from your apps
from inventory.views import ProductViewSet
from inbound.views import SupplierViewSet, InboundViewSet
from outbound.views import CustomerViewSet, OutboundViewSet
from core.views import AttachmentViewSet, ActivityLogViewSet
from users.views import UserViewSet, UserRegistrationView, RoleViewSet, RolePermissionView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

# Create a single router for the entire API
router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'inbounds', InboundViewSet, basename='inbound')
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'outbounds', OutboundViewSet, basename='outbound')
router.register(r'attachments', AttachmentViewSet, basename='attachment')
router.register(r'users', UserViewSet, basename='user')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'activity-logs', ActivityLogViewSet, basename='activity-log')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),  # Unified API root

    # JWT Authentication endpoints
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # Public registration endpoint
    path('api/register/', UserRegistrationView.as_view(), name='register'),

    # Role-Permission management endpoint
    path('api/roles/<int:role_id>/permissions/', RolePermissionView.as_view(), name='role-permissions'),

    path('api/dashboard/', include('dashboard.urls')),
]

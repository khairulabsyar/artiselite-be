from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CustomerViewSet, OutboundViewSet

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'outbounds', OutboundViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

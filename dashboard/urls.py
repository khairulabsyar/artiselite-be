from django.urls import path
from .views import DashboardSummary, RecentActivity, TransactionVolume

urlpatterns = [
    path('summary/', DashboardSummary.as_view(), name='dashboard-summary'),
    path('activity/', RecentActivity.as_view(), name='dashboard-activity'),
    path('transaction-volume/', TransactionVolume.as_view(), name='dashboard-transaction-volume'),
]
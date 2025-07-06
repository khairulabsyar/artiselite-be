from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import F
from datetime import date, timedelta
from .serializers import ActivityLogSerializer, TransactionVolumeSerializer
from inventory.models import Product
from inbound.models import Inbound
from outbound.models import Outbound
from auditlog.models import LogEntry


class DashboardSummary(APIView):
    def get(self, request):
        total_items = Product.objects.filter(is_archived=False).count()
        today = date.today()
        today_inbound = Inbound.objects.filter(inbound_date=today, status='COMPLETED').count()
        today_outbound = Outbound.objects.filter(outbound_date=today, status='COMPLETED').count()
        low_stock = Product.objects.filter(
            quantity__lte=F('low_stock_threshold'),
            is_archived=False
        ).count()
        
        return Response({
            'total_inventory_items': total_items,
            'today_inbound': today_inbound,
            'today_outbound': today_outbound,
            'low_stock_alerts': low_stock
        })

class RecentActivity(APIView):
    def get(self, request):
        activities = LogEntry.objects.order_by('-timestamp')[:20]
        serializer = ActivityLogSerializer(activities, many=True)
        return Response(serializer.data)

class TransactionVolume(APIView):
    def get(self, request):
        days = int(request.query_params.get('days', 7))
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)  # Inclusive of today

        data = []
        date_range = [start_date + timedelta(days=x) for x in range(days)]

        for single_date in date_range:
            inbound_count = Inbound.objects.filter(
                inbound_date=single_date, status='COMPLETED'
            ).count()

            outbound_count = Outbound.objects.filter(
                outbound_date=single_date, status='COMPLETED'
            ).count()

            data.append({
                'date': single_date,
                'inbound': inbound_count,
                'outbound': outbound_count
            })

        serializer = TransactionVolumeSerializer(data, many=True)
        return Response(serializer.data)
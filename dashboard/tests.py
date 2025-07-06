from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from datetime import date, timedelta

from inventory.models import Product
from inbound.models import Inbound, Supplier
from outbound.models import Outbound, Customer
from auditlog.models import LogEntry

User = get_user_model()

class DashboardAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)

        # Create related objects
        self.supplier = Supplier.objects.create(name='Test Supplier', email='supplier@test.com')
        self.customer = Customer.objects.create(name='Test Customer', email='customer@test.com')

        # Create test data
        # Products
        self.product_a = Product.objects.create(name='Product A', sku='PROD-A', quantity=100, low_stock_threshold=20)
        self.product_b = Product.objects.create(name='Product B', sku='PROD-B', quantity=15, low_stock_threshold=20)
        Product.objects.create(name='Product C', sku='PROD-C', quantity=50, low_stock_threshold=10, is_archived=True)

        # Inbound/Outbound
        today = date.today()
        yesterday = today - timedelta(days=1)
        Inbound.objects.create(supplier=self.supplier, inbound_date=today, status='COMPLETED')
        Inbound.objects.create(supplier=self.supplier, inbound_date=today, status='PENDING')
        Outbound.objects.create(customer=self.customer, product=self.product_a, quantity=5, outbound_date=today, status='COMPLETED')
        Outbound.objects.create(customer=self.customer, product=self.product_b, quantity=10, outbound_date=yesterday, status='COMPLETED')

        # Activity Logs (LogEntry)
        product_content_type = ContentType.objects.get_for_model(Product)
        for i in range(25):
            LogEntry.objects.create(
                actor=self.user,
                content_type=product_content_type,
                object_id=self.product_a.id,
                object_repr=str(self.product_a),
                action=LogEntry.Action.CREATE,
                changes='{}'
            )

    def test_get_dashboard_summary(self):
        url = reverse('dashboard-summary')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data['total_inventory_items'], 2)
        self.assertEqual(data['today_inbound'], 1)
        self.assertEqual(data['today_outbound'], 1)
        self.assertEqual(data['low_stock_alerts'], 1)

    def test_get_dashboard_activity(self):
        url = reverse('dashboard-activity')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 20)

    def test_get_transaction_volume(self):
        # This test is more complex as it depends on InventoryLog, which we haven't mocked.
        # For now, we'll test the structure and that it returns data for the requested days.
        url = reverse('dashboard-transaction-volume') + '?days=5'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)

import os
import json
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from .models import Supplier, Inbound, InboundItem
from inventory.models import Product, InventoryLog
from core.models import Attachment

User = get_user_model()

class InboundAPITests(APITestCase):
    """
    Test suite for the Inbound API endpoints.
    """

    def setUp(self):
        """
        Set up the test environment.
        """
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)

        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            email='supplier@test.com'
        )
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST001',
            quantity=100
        )
        self.inbound_list_url = reverse('inbound-list')

    def tearDown(self):
        """
        Clean up created files.
        """
        for attachment in Attachment.objects.all():
            if attachment.file and os.path.exists(attachment.file.path):
                os.remove(attachment.file.path)

    def test_create_inbound_with_attachment(self):
        """
        Ensure we can create a new inbound shipment with an attachment.
        """
        # Create a dummy file for upload
        dummy_file = SimpleUploadedFile("invoice.pdf", b"file_content", content_type="application/pdf")

        items_data = [
            {
                'product_id': self.product.id,
                'quantity': 10,
                'unit_price': '50.00'
            }
        ]

        data = {
            'supplier_id': self.supplier.id,
            'inbound_date': '2024-01-01',
            'notes': 'Test inbound with attachment',
            'items': json.dumps(items_data),
            'uploaded_attachments': [dummy_file]
        }

        response = self.client.post(self.inbound_list_url, data, format='multipart')


        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Inbound.objects.count(), 1)
        self.assertEqual(InboundItem.objects.count(), 1)

        inbound = Inbound.objects.first()
        self.assertEqual(inbound.attachments.count(), 1)
        attachment = inbound.attachments.first()
        self.assertTrue(attachment.file.name.endswith('invoice.pdf'))

    def test_create_inbound_without_attachment(self):
        """
        Ensure we can create a new inbound shipment without an attachment.
        """
        items_data = [
            {
                'product_id': self.product.id,
                'quantity': 10,
                'unit_price': '50.00'
            }
        ]

        data = {
            'supplier_id': self.supplier.id,
            'inbound_date': '2024-01-01',
            'notes': 'Test inbound without attachment',
            'items': json.dumps(items_data)
        }

        response = self.client.post(self.inbound_list_url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Inbound.objects.count(), 1)
        self.assertEqual(Inbound.objects.first().attachments.count(), 0)

    def test_complete_inbound_updates_inventory(self):
        """
        Ensure completing an inbound shipment correctly updates product quantity and creates an inventory log.
        """
        inbound = Inbound.objects.create(
            supplier=self.supplier,
            inbound_date='2024-01-02',
            status='PENDING'
        )
        InboundItem.objects.create(
            inbound=inbound,
            product=self.product,
            quantity=50,
            unit_price=45.00
        )

        initial_quantity = self.product.quantity
        initial_log_count = InventoryLog.objects.count()

        # Update the status to COMPLETED
        update_url = reverse('inbound-detail', kwargs={'pk': inbound.pk})
        response = self.client.patch(update_url, {'status': 'COMPLETED'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh objects from DB
        self.product.refresh_from_db()
        inbound.refresh_from_db()

        self.assertEqual(inbound.status, 'COMPLETED')
        self.assertEqual(self.product.quantity, initial_quantity + 50)
        self.assertEqual(InventoryLog.objects.count(), initial_log_count + 1)

        latest_log = InventoryLog.objects.latest('timestamp')
        self.assertEqual(latest_log.product, self.product)
        self.assertEqual(latest_log.quantity_change, 50)
        self.assertEqual(latest_log.new_quantity, self.product.quantity)
        self.assertIn(f'Inbound shipment #{inbound.id} completed', latest_log.reason)

    def test_bulk_upload_inbound(self):
        """
        Ensure we can bulk upload inbound shipments using a CSV file.
        """
        csv_content = (
            'inbound_ref,inbound_date,supplier_email,product_sku,quantity,unit_price\n'
            'BULK-001,2024-01-03,supplier@test.com,TEST001,25,10.00\n'
        )
        csv_file = SimpleUploadedFile("bulk.csv", csv_content.encode('utf-8'), content_type="text/csv")

        upload_url = reverse('inbound-bulk-upload')
        response = self.client.post(upload_url, {'file': csv_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'Bulk upload successful')
        self.assertEqual(Inbound.objects.count(), 1)
        self.assertEqual(InboundItem.objects.count(), 1)
        self.assertEqual(Inbound.objects.first().status, 'PENDING')
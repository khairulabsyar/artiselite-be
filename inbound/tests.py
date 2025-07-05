import io
import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from inventory.models import InventoryLog, Product
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Inbound, InboundItem, Supplier

User = get_user_model()

class InboundAPITests(APITestCase):
    """Test suite for the Inbound and Supplier APIs."""

    def setUp(self):
        """Set up the necessary objects for testing."""
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)

        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            email='supplier@test.com',
            phone='1234567890'
        )
        self.product = Product.objects.create(
            name='Test Product',
            sku='SKU123',
            quantity=10,
            low_stock_threshold=5
        )

    def test_create_inbound_shipment(self):
        """Ensure we can create a new inbound shipment."""
        url = reverse('inbound-list')
        data = {
            'supplier_id': self.supplier.id,
            'inbound_date': '2024-01-01',
            'status': 'PENDING',
            'items': [
                {
                    'product_id': self.product.id,
                    'quantity': 5,
                    'unit_price': '10.00'
                }
            ]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Inbound.objects.count(), 1)
        self.assertEqual(InboundItem.objects.count(), 1)
        
        # Check that inventory is not yet updated
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 10)

    def test_complete_inbound_shipment_updates_inventory(self):
        """Ensure completing an inbound shipment updates product quantity and creates a log."""
        inbound = Inbound.objects.create(supplier=self.supplier, inbound_date='2024-01-02', status='PENDING')
        InboundItem.objects.create(inbound=inbound, product=self.product, quantity=5, unit_price=10.00)
        
        initial_quantity = self.product.quantity

        url = reverse('inbound-detail', kwargs={'pk': inbound.pk})
        response = self.client.patch(url, {'status': 'COMPLETED'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, initial_quantity + 5)
        
        # Check if InventoryLog was created
        log_exists = InventoryLog.objects.filter(
            product=self.product,
            quantity_change=5,
            new_quantity=initial_quantity + 5
        ).exists()
        self.assertTrue(log_exists)

    def test_prevent_double_counting_on_repeated_completion(self):
        """Ensure inventory is not updated again if an already completed shipment is updated."""
        inbound = Inbound.objects.create(supplier=self.supplier, inbound_date='2024-01-03', status='PENDING')
        InboundItem.objects.create(inbound=inbound, product=self.product, quantity=5, unit_price=10.00)

        # First completion
        inbound.status = 'COMPLETED'
        inbound.save() # This triggers the inventory update
        self.product.refresh_from_db()
        quantity_after_first_completion = self.product.quantity
        self.assertEqual(quantity_after_first_completion, 15)

        # Try to update again (e.g., changing notes)
        url = reverse('inbound-detail', kwargs={'pk': inbound.pk})
        response = self.client.patch(url, {'notes': 'An additional note.'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, quantity_after_first_completion)
        self.assertEqual(InventoryLog.objects.filter(product=self.product).count(), 1)

    def test_create_inbound_with_attachment(self):
        """Test creating an inbound shipment with a file attachment."""
        url = reverse('inbound-list')
        # Create a file attachment for testing
        attachment = SimpleUploadedFile("invoice.pdf", b"file_content", content_type="application/pdf")
        
        # Simplify - use a single file upload as Django REST Framework expects
        data = {
            'supplier_id': self.supplier.id,
            'inbound_date': '2024-01-04',
            'status': 'PENDING',
            'items': json.dumps([{'product_id': self.product.id, 'quantity': 1, 'unit_price': '1.00'}]),
            'uploaded_attachments': attachment  # Direct file, not in list
        }
        
        response = self.client.post(url, data, format='multipart')
        if response.status_code != status.HTTP_201_CREATED:
            print("Response data:", response.data)
            print("Request data type:", type(data['uploaded_attachments']))
            
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        inbound = Inbound.objects.get(pk=response.data['id'])
        self.assertEqual(inbound.attachments.count(), 1)
        self.assertEqual(inbound.attachments.first().original_filename, 'invoice.pdf')

    def test_bulk_upload_inbounds_success(self):
        """Test bulk uploading inbound shipments from a CSV file."""
        url = reverse('inbound-bulk-upload')
        csv_data = (
            'inbound_ref,inbound_date,supplier_email,product_sku,quantity,unit_price\n'
            'REF001,2024-01-05,supplier@test.com,SKU123,10,15.00\n'
        )
        csv_file = io.StringIO(csv_data)
        file = SimpleUploadedFile("bulk.csv", csv_file.read().encode('utf-8'), content_type="text/csv")
        
        response = self.client.post(url, {'file': file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Inbound.objects.filter(notes='Bulk upload ref: REF001').count(), 1)
        self.assertTrue(InboundItem.objects.filter(quantity=10).exists())

    def test_bulk_upload_fail_missing_column(self):
        """Test that bulk upload fails if a required column is missing."""
        url = reverse('inbound-bulk-upload')
        csv_data = 'inbound_ref,inbound_date,product_sku,quantity\nREF002,2024-01-06,SKU123,5\n'
        csv_file = io.StringIO(csv_data)
        file = SimpleUploadedFile("bulk_fail.csv", csv_file.read().encode('utf-8'), content_type="text/csv")
        
        response = self.client.post(url, {'file': file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing required columns', response.data['error'])

    def test_bulk_upload_fail_invalid_sku(self):
        """Test that bulk upload fails for a non-existent product SKU."""
        url = reverse('inbound-bulk-upload')
        csv_data = (
            'inbound_ref,inbound_date,supplier_email,product_sku,quantity,unit_price\n'
            'REF003,2024-01-07,supplier@test.com,SKU_NONEXISTENT,10,15.00\n'
        )
        csv_file = io.StringIO(csv_data)
        file = SimpleUploadedFile("bulk_fail_sku.csv", csv_file.read().encode('utf-8'), content_type="text/csv")
        
        response = self.client.post(url, {'file': file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid data', response.data['error'])
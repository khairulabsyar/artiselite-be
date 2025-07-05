import os
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from inventory.models import Product, InventoryLog
from .models import Customer, Outbound, Attachment

class OutboundAPITests(APITestCase):
    def setUp(self):
        """Set up initial data for tests."""
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.login(username='testuser', password='testpassword')

        self.product = Product.objects.create(
            name='Test Product',
            sku='TP001',
            category='Electronics',
            quantity=100,
            low_stock_threshold=10
        )
        self.customer = Customer.objects.create(
            name='Test Customer',
            email='customer@example.com',
            phone='1234567890'
        )
        self.outbound = Outbound.objects.create(
            customer=self.customer,
            product=self.product,
            quantity=10,
            outbound_date='2025-07-05',
            status='PENDING',
            so_ref='SO-INITIAL'
        )

    def test_create_customer(self):
        """Ensure we can create a new customer."""
        url = reverse('customer-list')
        data = {'name': 'New Customer', 'email': 'new@example.com', 'phone': '9876543210'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Customer.objects.count(), 2)

    def test_list_outbounds(self):
        """Ensure we can list outbound records."""
        url = reverse('outbound-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_outbound(self):
        """Ensure we can retrieve a single outbound record."""
        url = reverse('outbound-detail', kwargs={'pk': self.outbound.pk})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['so_ref'], 'SO-INITIAL')

    def test_create_outbound(self):
        """Ensure we can create a new outbound record.

        This also checks that creating a 'PENDING' outbound does not immediately
        deduct from inventory.
        """
        url = reverse('outbound-list')
        data = {
            'customer': self.customer.id,
            'product': self.product.id,
            'quantity': 5,
            'outbound_date': '2025-07-06',
            'so_ref': 'SO123'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Outbound.objects.count(), 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 100)

    def test_create_outbound_insufficient_stock(self):
        """Ensure creating an outbound with insufficient stock fails."""
        url = reverse('outbound-list')
        data = {
            'customer': self.customer.id,
            'product': self.product.id,
            'quantity': 200,  # More than available
            'outbound_date': '2025-07-05'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Not enough stock', response.data['product'][0])

    def test_real_time_deduction_on_completion(self):
        """Ensure completing an outbound record deducts stock and creates a log."""
        initial_log_count = InventoryLog.objects.count()
        url = reverse('outbound-complete-outbound', kwargs={'pk': self.outbound.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 90)

        self.outbound.refresh_from_db()
        self.assertEqual(self.outbound.status, 'COMPLETED')

        # Check for inventory log entry
        self.assertEqual(InventoryLog.objects.count(), initial_log_count + 1)
        log = InventoryLog.objects.latest('timestamp')
        self.assertEqual(log.product, self.product)
        self.assertEqual(log.quantity_change, -10)


    def test_create_outbound_with_attachment(self):
        """Ensure we can create an outbound with a file attachment."""
        url = reverse('outbound-list')
        attachment_file = SimpleUploadedFile("do.pdf", b"signed_do_content", content_type="application/pdf")
        data = {
            'customer': self.customer.id,
            'product': self.product.id,
            'quantity': 5,
            'outbound_date': '2025-07-05',
            'so_ref': 'SO-ATTACH',
            'uploaded_attachments': [attachment_file]
        }
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_outbound = Outbound.objects.get(so_ref='SO-ATTACH')
        self.assertEqual(new_outbound.attachments.count(), 1)
        self.assertTrue(new_outbound.attachments.exists())

    def test_bulk_upload_outbound_success(self):
        """Test successful bulk uploading of outbound records from a CSV file."""
        csv_content = (
            'product_sku,customer_email,quantity,outbound_date,so_ref\n'
            'TP001,customer@example.com,5,2025-07-05,SO456'
        )
        csv_file = SimpleUploadedFile("bulk.csv", csv_content.encode('utf-8'), content_type="text/csv")
        url = reverse('outbound-bulk-upload')

        initial_quantity = self.product.quantity
        response = self.client.post(url, {'file': csv_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Outbound.objects.count(), 2)  # Initial + bulk

        created_outbound = Outbound.objects.get(so_ref='SO456')
        self.assertEqual(created_outbound.quantity, 5)
        self.assertEqual(created_outbound.status, 'PENDING') # Bulk uploads are created as PENDING

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, initial_quantity) # Stock is not deducted on bulk upload

    def test_bulk_upload_outbound_insufficient_stock(self):
        """Test bulk uploading with insufficient stock fails for the specific row."""
        csv_content = (
            'product_sku,customer_email,quantity,outbound_date,so_ref\n'
            'TP001,customer@example.com,150,2025-07-05,SO789' # Fails
        )
        csv_file = SimpleUploadedFile("bulk_fail.csv", csv_content.encode('utf-8'), content_type="text/csv")
        url = reverse('outbound-bulk-upload')
        response = self.client.post(url, {'file': csv_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Not enough stock for', response.data['errors'][0])
        self.assertEqual(Outbound.objects.count(), 1) # No new outbound created

    def test_update_outbound(self):
        """Ensure we can update a pending outbound record."""
        url = reverse('outbound-detail', kwargs={'pk': self.outbound.pk})
        data = {'quantity': 15, 'so_ref': 'SO-UPDATED'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.outbound.refresh_from_db()
        self.assertEqual(self.outbound.quantity, 15)
        self.assertEqual(self.outbound.so_ref, 'SO-UPDATED')

    def test_delete_outbound(self):
        """Ensure we can delete a pending outbound record."""
        url = reverse('outbound-detail', kwargs={'pk': self.outbound.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Outbound.objects.count(), 0)

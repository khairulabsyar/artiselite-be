import csv
from io import BytesIO, StringIO

import pandas as pd
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import InventoryLog, Product

User = get_user_model()

class ProductViewSetTests(APITestCase):
    """
    Test suite for the ProductViewSet.
    """

    def setUp(self):
        """
        Set up the test environment.
        """
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.login(username='testuser', password='testpassword')

        self.product1 = Product.objects.create(
            name='Laptop', sku='LP100', category='Electronics', quantity=50, low_stock_threshold=10
        )
        self.product2 = Product.objects.create(
            name='Mouse', sku='MS200', category='Electronics', quantity=5, low_stock_threshold=10
        )
        self.product3 = Product.objects.create(
            name='Keyboard', sku='KB300', category='Peripherals', quantity=20, is_archived=True
        )

    def test_create_product_success(self):
        """
        Ensure we can create a new product.
        """
        url = reverse('product-list')
        data = {
            'name': 'New Monitor', 'sku': 'MN400', 'category': 'Electronics',
            'quantity': 30, 'low_stock_threshold': 5, 'reason': 'Initial stock-in'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 4)

        # Verify InventoryLog was created
        new_product = Product.objects.get(sku='MN400')
        log = InventoryLog.objects.get(product=new_product)
        self.assertEqual(log.quantity_change, 30)
        self.assertEqual(log.new_quantity, 30)
        self.assertEqual(log.reason, 'Initial stock-in')
        self.assertEqual(log.user, self.user)

    def test_create_product_duplicate_sku_fails(self):
        """
        Ensure creating a product with a duplicate SKU fails.
        """
        url = reverse('product-list')
        data = {'name': 'Another Laptop', 'sku': 'LP100', 'quantity': 10}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_products(self):
        """
        Ensure we can list all non-archived products.
        """
        url = reverse('product-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3) # Includes archived by default from viewset

    def test_filter_products_by_category(self):
        """
        Ensure we can filter products by category.
        """
        url = f"{reverse('product-list')}?category=Electronics"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertTrue(all(p['category'] == 'Electronics' for p in response.data))

    def test_search_products_by_name(self):
        """
        Ensure we can search for products by name.
        """
        url = f"{reverse('product-list')}?search=Laptop"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Laptop')

    def test_update_product_quantity(self):
        """
        Ensure updating a product's quantity creates an InventoryLog.
        """
        url = reverse('product-detail', kwargs={'pk': self.product1.pk})
        data = {'quantity': 45, 'reason': 'Sales order #123'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['quantity'], 45)

        # Verify InventoryLog
        log = InventoryLog.objects.filter(product=self.product1).latest('timestamp')
        self.assertEqual(log.quantity_change, -5) # 50 -> 45
        self.assertEqual(log.new_quantity, 45)
        self.assertEqual(log.reason, 'Sales order #123')

    def test_low_stock_endpoint(self):
        """
        Ensure the low_stock endpoint returns only products at or below the threshold.
        """
        url = reverse('product-low-stock')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['sku'], 'MS200') # Only Mouse is low stock

    def _create_test_file(self, data, file_format='csv'):
        """
        Helper to create an in-memory file for testing uploads.
        """
        if file_format == 'csv':
            output = StringIO()
            # Define all possible headers to handle varied data rows
            fieldnames = ['sku', 'name', 'quantity', 'category']
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
            output.seek(0)
            return SimpleUploadedFile("test.csv", output.read().encode('utf-8'), content_type="text/csv")
        elif file_format == 'xlsx':
            output = BytesIO()
            df = pd.DataFrame(data)
            df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            return SimpleUploadedFile("test.xlsx", output.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def test_bulk_upload_create_and_update(self):
        """
        Ensure bulk upload can create new products and update existing ones.
        """
        url = reverse('product-bulk-upload')
        upload_data = [
            {'sku': 'LP100', 'name': 'Laptop Pro', 'quantity': 60}, # Update
            {'sku': 'PRJ500', 'name': 'Projector', 'quantity': 15, 'category': 'Electronics'} # Create
        ]
        file = self._create_test_file(upload_data, file_format='csv')
        response = self.client.post(url, {'file': file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created'], 1)
        self.assertEqual(response.data['updated'], 1)

        # Verify update
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.name, 'Laptop Pro')
        self.assertEqual(self.product1.quantity, 60)

        # Verify creation
        new_product = Product.objects.get(sku='PRJ500')
        self.assertEqual(new_product.name, 'Projector')
        self.assertEqual(new_product.quantity, 15)

        # Verify logs
        update_log = InventoryLog.objects.get(product=self.product1, reason__contains='Bulk upload')
        self.assertEqual(update_log.quantity_change, 10)
        create_log = InventoryLog.objects.get(product=new_product, reason__contains='Bulk upload')
        self.assertEqual(create_log.quantity_change, 15)

    def test_bulk_upload_missing_columns_fails(self):
        """
        Ensure bulk upload fails if required columns are missing.
        """
        url = reverse('product-bulk-upload')
        # Create a CSV that is explicitly missing the 'name' column header
        csv_content = "sku,quantity\nSKU-FAIL,10"
        file = SimpleUploadedFile("fail.csv", csv_content.encode('utf-8'), content_type="text/csv")
        response = self.client.post(url, {'file': file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing required columns', response.data['error'])

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase
from apps.catalog.models import Category, Product
from apps.orders.models import Order, OrderItem
from apps.orders.services import create_order, process_payment_success, process_payment_failure
from apps.payments.models import Payment

User = get_user_model()

class OrderServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='customer@example.com', username='customer', password='password123'
        )
        self.category = Category.objects.create(name='Gadgets')
        self.prod_a = Product.objects.create(
            sku='PRODA', name='Product A', price=10.00, stock=50, status='active', category=self.category
        )
        self.prod_b = Product.objects.create(
            sku='PRODB', name='Product B', price=25.50, stock=20, status='active', category=self.category
        )
        self.inactive_prod = Product.objects.create(
            sku='PRODC', name='Product C', price=5.00, stock=10, status='inactive', category=self.category
        )

    def test_order_creation_deterministic_calculation(self):
        items_data = [
            {'product_id': self.prod_a.id, 'quantity': 3},
            {'product_id': self.prod_b.id, 'quantity': 2}
        ]
        order = create_order(self.user, items_data)
        
        # Subtotals:
        # Prod A: 3 * 10 = 30.00
        # Prod B: 2 * 25.50 = 51.00
        # Total: 81.00
        self.assertEqual(order.total_amount, 81.00)
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.items.count(), 2)
        
        item_a = order.items.get(product=self.prod_a)
        self.assertEqual(item_a.price, 10.00)
        self.assertEqual(item_a.subtotal, 30.00)

    def test_order_creation_invalid_inactive_product(self):
        items_data = [
            {'product_id': self.inactive_prod.id, 'quantity': 1}
        ]
        with self.assertRaises(ValidationError):
            create_order(self.user, items_data)

    def test_safe_stock_reduction_success(self):
        items_data = [
            {'product_id': self.prod_a.id, 'quantity': 5},
            {'product_id': self.prod_b.id, 'quantity': 2}
        ]
        order = create_order(self.user, items_data)
        payment = Payment.objects.create(
            order=order,
            provider='stripe',
            transaction_id='tx_test_123',
            status='pending'
        )

        process_payment_success(payment.id)
        
        # Reload models
        self.prod_a.refresh_from_db()
        self.prod_b.refresh_from_db()
        payment.refresh_from_db()
        order.refresh_from_db()
        
        # Stock should decrease:
        # A: 50 - 5 = 45
        # B: 20 - 2 = 18
        self.assertEqual(self.prod_a.stock, 45)
        self.assertEqual(self.prod_b.stock, 18)
        self.assertEqual(payment.status, 'success')
        self.assertEqual(order.status, 'paid')

    def test_safe_stock_reduction_insufficient_stock_rollback(self):
        # Request more stock than available for prod_b (25 requested, only 20 available)
        items_data = [
            {'product_id': self.prod_a.id, 'quantity': 5},
            {'product_id': self.prod_b.id, 'quantity': 25}
        ]
        order = create_order(self.user, items_data)
        payment = Payment.objects.create(
            order=order,
            provider='stripe',
            transaction_id='tx_test_failed_stock',
            status='pending'
        )

        # Execution should raise ValidationError and roll back entire stock deduction
        with self.assertRaises(ValidationError):
            process_payment_success(payment.id)
            
        # Reload models
        self.prod_a.refresh_from_db()
        self.prod_b.refresh_from_db()
        
        # Stocks should remain unchanged
        self.assertEqual(self.prod_a.stock, 50)
        self.assertEqual(self.prod_b.stock, 20)


class OrderAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='customer@example.com', username='customer', password='password123'
        )
        self.category = Category.objects.create(name='Gadgets')
        self.prod = Product.objects.create(
            sku='PROD1', name='Product 1', price=10.00, stock=50, status='active', category=self.category
        )
        # Login
        token_url = reverse('auth_login')
        login_res = self.client.post(token_url, {'email': 'customer@example.com', 'password': 'password123'})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_res.data['access']}")
        self.order_url = reverse('order-list')

    def test_create_order_via_api(self):
        post_data = {
            'items': [
                {'product_id': self.prod.id, 'quantity': 2}
            ]
        }
        response = self.client.post(self.order_url, post_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(response.data['total_amount']), 20.00)
        self.assertEqual(response.data['status'], 'pending')

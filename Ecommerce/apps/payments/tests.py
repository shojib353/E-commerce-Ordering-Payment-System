from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.catalog.models import Category, Product
from apps.orders.models import Order
from apps.orders.services import create_order
from apps.payments.models import Payment
from apps.payments.strategies import PaymentContext, StripePaymentStrategy, BkashPaymentStrategy

User = get_user_model()

@override_settings(STRIPE_SECRET_KEY='stripe_placeholder_key', BKASH_APP_KEY='bkash_placeholder_key')
class PaymentStrategyTests(TestCase):
    def test_payment_context_strategy_selection(self):
        context_stripe = PaymentContext('stripe')
        self.assertIsInstance(context_stripe.strategy, StripePaymentStrategy)
        
        context_bkash = PaymentContext('bkash')
        self.assertIsInstance(context_bkash.strategy, BkashPaymentStrategy)
        
        with self.assertRaises(ValueError):
            PaymentContext('unsupported_provider')


@override_settings(STRIPE_SECRET_KEY='stripe_placeholder_key', BKASH_APP_KEY='bkash_placeholder_key')
class PaymentAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='shopper@example.com', username='shopper', password='password123'
        )
        self.category = Category.objects.create(name='Gadgets')
        self.product = Product.objects.create(
            sku='PROD100', name='Product 100', price=100.00, stock=10, status='active', category=self.category
        )
        # Login
        token_url = reverse('auth_login')
        login_res = self.client.post(token_url, {'email': 'shopper@example.com', 'password': 'password123'})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_res.data['access']}")
        
        # Create order
        self.order = create_order(self.user, [{'product_id': self.product.id, 'quantity': 1}])
        self.initiate_url = reverse('payment_initiate')
        self.execute_url = reverse('payment_execute')

    def test_initiate_stripe_payment(self):
        post_data = {
            'order_id': self.order.id,
            'provider': 'stripe'
        }
        response = self.client.post(self.initiate_url, post_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'pending')
        self.assertIn('client_secret', response.data)
        
        # Check payment record creation
        payment_exists = Payment.objects.filter(
            order=self.order, provider='stripe', transaction_id=response.data['transaction_id']
        ).exists()
        self.assertTrue(payment_exists)

    def test_initiate_bkash_payment(self):
        post_data = {
            'order_id': self.order.id,
            'provider': 'bkash'
        }
        response = self.client.post(self.initiate_url, post_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'pending')
        self.assertIn('payment_url', response.data)
        
        payment_exists = Payment.objects.filter(
            order=self.order, provider='bkash', transaction_id=response.data['transaction_id']
        ).exists()
        self.assertTrue(payment_exists)

    def test_execute_payment_success(self):
        # Initiate a stripe payment first
        init_res = self.client.post(self.initiate_url, {'order_id': self.order.id, 'provider': 'stripe'})
        payment_id = init_res.data['payment_id']
        
        # Execute it
        exec_res = self.client.post(self.execute_url, {'payment_id': payment_id})
        self.assertEqual(exec_res.status_code, status.HTTP_200_OK)
        self.assertEqual(exec_res.data['status'], 'success')
        
        # Verify order paid and stock reduced
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.product.stock, 9)


@override_settings(STRIPE_SECRET_KEY='stripe_placeholder_key', BKASH_APP_KEY='bkash_placeholder_key')
class WebhookAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='shopper2@example.com', username='shopper2', password='password123'
        )
        self.category = Category.objects.create(name='Gadgets')
        self.product = Product.objects.create(
            sku='PROD200', name='Product 200', price=50.00, stock=5, status='active', category=self.category
        )
        self.order = create_order(self.user, [{'product_id': self.product.id, 'quantity': 2}])
        
        # Create a payment record representing an initiated Stripe checkout
        self.payment = Payment.objects.create(
            order=self.order,
            provider='stripe',
            transaction_id='stripe_pi_test_webhook_123',
            status='pending'
        )
        self.stripe_webhook_url = reverse('payment_webhook_stripe')
        self.bkash_webhook_url = reverse('payment_webhook_bkash')

    def test_stripe_webhook_payment_intent_succeeded(self):
        # Send mock succeeded event payload to webhook
        payload = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': 'stripe_pi_test_webhook_123',
                    'status': 'succeeded',
                    'amount': 10000
                }
            }
        }
        response = self.client.post(self.stripe_webhook_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify statuses and stock
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        
        self.assertEqual(self.payment.status, 'success')
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.product.stock, 3) # 5 - 2 = 3

    def test_stripe_webhook_payment_intent_failed(self):
        payload = {
            'type': 'payment_intent.payment_failed',
            'data': {
                'object': {
                    'id': 'stripe_pi_test_webhook_123',
                    'status': 'failed'
                }
            }
        }
        response = self.client.post(self.stripe_webhook_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify statuses and stock
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        
        self.assertEqual(self.payment.status, 'failed')
        self.assertEqual(self.order.status, 'canceled')
        self.assertEqual(self.product.stock, 5) # Unchanged

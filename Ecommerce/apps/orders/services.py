from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import F
from apps.orders.models import Order, OrderItem
from apps.catalog.models import Product
from apps.payments.models import Payment
import logging

logger = logging.getLogger(__name__)

def create_order(user, items_data) -> Order:
    """
    Creates an order, calculating subtotals and totals deterministically.
    Items data format: [{'product_id': int, 'quantity': int}, ...]
    Note: Stock is NOT reduced yet; it is reduced only after successful payment.
    """
    if not items_data:
        raise ValidationError("An order must contain at least one item.")

    with transaction.atomic():
        order = Order.objects.create(user=user, status='pending', total_amount=Decimal('0.00'))
        total_amount = Decimal('0.00')
        
        for item in items_data:
            product_id = item.get('product_id')
            quantity = item.get('quantity')
            
            if not product_id or not quantity or quantity <= 0:
                raise ValidationError("Invalid product ID or quantity.")
                
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                raise ValidationError(f"Product with ID {product_id} does not exist.")
                
            if product.status != 'active':
                raise ValidationError(f"Product '{product.name}' is currently inactive.")
                
            # Deterministic subtotal calculation
            subtotal = product.price * quantity
            total_amount += subtotal
            
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=product.price,
                subtotal=subtotal
            )
            
        order.total_amount = total_amount
        order.save()
        return order


def process_payment_success(payment_id: int):
    """
    Safely process payment success with select_for_update to avoid race conditions.
    Reduces the product stock and updates order and payment statuses.
    """
    with transaction.atomic():
        # Lock the payment record
        try:
            payment = Payment.objects.select_for_update().get(id=payment_id)
        except Payment.DoesNotExist:
            logger.error(f"Payment with ID {payment_id} not found during success processing.")
            return

        if payment.status == 'success':
            logger.info(f"Payment #{payment.id} already processed as success.")
            return

        # Lock the order record
        order = Order.objects.select_for_update().get(id=payment.order_id)
        
        # Verify and reduce stock for all order items
        order_items = OrderItem.objects.filter(order=order).select_related('product')
        
        # We need to lock the products to prevent concurrent stock reduction issues
        product_ids = [item.product_id for item in order_items]
        # Lock products in a consistent order to avoid deadlocks
        locked_products = {
            p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids).order_by('id')
        }
        
        # Check stock for all items first
        for item in order_items:
            product = locked_products.get(item.product_id)
            if not product:
                raise ValidationError(f"Product {item.product.name} not found during processing.")
            if product.stock < item.quantity:
                raise ValidationError(
                    f"Insufficient stock for product '{product.name}'. "
                    f"Available: {product.stock}, Ordered: {item.quantity}"
                )

        # Deduct stock and save
        for item in order_items:
            product = locked_products.get(item.product_id)
            product.stock = F('stock') - item.quantity
            product.save()
            
        # Update payment and order statuses
        payment.status = 'success'
        payment.save()
        
        order.status = 'paid'
        order.save()
        logger.info(f"Order #{order.id} paid successfully, payment #{payment.id}.")


def process_payment_failure(payment_id: int):
    """
    Process payment failure, updating statuses accordingly.
    """
    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(id=payment_id)
        except Payment.DoesNotExist:
            logger.error(f"Payment with ID {payment_id} not found during failure processing.")
            return

        if payment.status == 'failed':
            return

        payment.status = 'failed'
        payment.save()

        # Update order status to canceled
        order = Order.objects.select_for_update().get(id=payment.order_id)
        order.status = 'canceled'
        order.save()
        logger.info(f"Order #{order.id} marked as canceled due to payment #{payment.id} failure.")

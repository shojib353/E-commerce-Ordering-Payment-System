from django.db import models
from django.conf import settings
from apps.catalog.models import Product

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('canceled', 'Canceled'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='orders'
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'Orders'

    def __str__(self):
        return f"Order #{self.id} - {self.user.email} - {self.status}"

class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.PROTECT, 
        related_name='order_items'
    )
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2) # Price at which product was ordered
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'OrderItems'

    def __str__(self):
        return f"Item: {self.product.name} x {self.quantity} in Order #{self.order.id}"

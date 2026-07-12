from django.db import models
from apps.orders.models import Order

class Payment(models.Model):
    PROVIDER_CHOICES = [
        ('stripe', 'Stripe'),
        ('bkash', 'bKash'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    order = models.ForeignKey(
        Order, 
        on_delete=models.PROTECT, 
        related_name='payments'
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, db_index=True)
    transaction_id = models.CharField(max_length=255, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    raw_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'Payments'

    def __str__(self):
        return f"Payment #{self.id} ({self.provider}) - Order #{self.order.id} - {self.status}"

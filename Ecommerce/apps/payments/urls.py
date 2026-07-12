from django.urls import path
from apps.payments.views import (
    PaymentInitiateView,
    PaymentExecuteView,
    StripeWebhookView,
    BkashWebhookView,
)

urlpatterns = [
    path('initiate/', PaymentInitiateView.as_view(), name='payment_initiate'),
    path('execute/', PaymentExecuteView.as_view(), name='payment_execute'),
    path('webhook/stripe/', StripeWebhookView.as_view(), name='payment_webhook_stripe'),
    path('webhook/bkash/', BkashWebhookView.as_view(), name='payment_webhook_bkash'),
]

from rest_framework import serializers
from apps.payments.models import Payment

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            'id', 'order', 'provider', 'transaction_id', 
            'status', 'created_at', 'updated_at'
        )


class PaymentInitiateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=[('stripe', 'Stripe'), ('bkash', 'bKash')])


class PaymentExecuteSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()

from rest_framework import serializers
from apps.orders.models import Order, OrderItem
from apps.catalog.serializers import ProductSerializer

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'quantity', 'price', 'subtotal')


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'user', 'total_amount', 'status', 'items', 
            'created_at', 'updated_at'
        )


class OrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class OrderCreateSerializer(serializers.Serializer):
    items = OrderItemCreateSerializer(many=True)

    def create(self, validated_data):
        user = self.context['request'].user
        items_data = validated_data['items']
        
        # Import create_order service
        from apps.orders.services import create_order
        try:
            return create_order(user, items_data)
        except Exception as e:
            raise serializers.ValidationError(str(e))

    def to_representation(self, instance):
        return OrderSerializer(instance, context=self.context).data

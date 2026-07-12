from rest_framework import serializers
from apps.catalog.models import Category, Product

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'parent', 'created_at', 'updated_at')

class ProductSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',
        required=False,
        allow_null=True
    )
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = (
            'id', 'sku', 'name', 'description', 'price', 'stock', 'status', 
            'category_id', 'category', 'created_at', 'updated_at'
        )

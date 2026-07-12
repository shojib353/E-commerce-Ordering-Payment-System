from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from apps.catalog.models import Category, Product
from apps.catalog.serializers import CategorySerializer, ProductSerializer
from apps.catalog.services import get_category_descendants_dfs

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]
    
    

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'recommendations', 'category_products']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        queryset = Product.objects.filter(status='active').order_by('-created_at')
        
        # Admins can see inactive products in list view
        if self.request.user and self.request.user.is_staff:
            queryset = Product.objects.all().order_by('-created_at')

        category_id = self.request.query_params.get('category_id')
        if category_id:
            try:
                cat_id = int(category_id)
                # Traverse tree using DFS and cache
                descendants = get_category_descendants_dfs(cat_id)
                queryset = queryset.filter(category_id__in=descendants)
            except ValueError:
                pass
                
        return queryset

    @action(detail=True, methods=['get'])
    def recommendations(self, request, pk=None):
        """
        Recommend related products in the same category hierarchy sub-tree using DFS.
        """
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        if not product.category:
            # Fallback: recommend other active products
            related = Product.objects.filter(status='active').exclude(id=product.id)[:5]
            serializer = self.get_serializer(related, many=True)
            return Response(serializer.data)

        # Retrieve all categories in the sub-tree of the product's category using DFS
        descendant_cat_ids = get_category_descendants_dfs(product.category_id)
        
        # Fetch up to 5 active products in this sub-hierarchy, excluding the product itself
        related_products = Product.objects.filter(
            status='active',
            category_id__in=descendant_cat_ids
        ).exclude(id=product.id).order_by('-created_at')[:5]
        
        serializer = self.get_serializer(related_products, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get products by category",
        description="Retrieve products belonging to the specified category, including descendants.",
        parameters=[
            OpenApiParameter(
                name='category_id',
                type=int,
                location=OpenApiParameter.PATH,
                description='Filter products by category ID (includes descendants)',
            )
        ]
    )
    @action(detail=False, methods=['get'], url_path='(?P<category_id>[0-9]+)/category')
    def category_products(self, request, category_id=None):
        try:
            cat_id = int(category_id)
        except ValueError:
            return Response({'error': 'Invalid category ID'}, status=status.HTTP_400_BAD_REQUEST)
            
        if not Category.objects.filter(id=cat_id).exists():
            return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)

        descendants = get_category_descendants_dfs(cat_id)
        queryset = Product.objects.filter(status='active').order_by('-created_at')
        if request.user and request.user.is_staff:
            queryset = Product.objects.all().order_by('-created_at')
        
        queryset = queryset.filter(category_id__in=descendants)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

from django.test import TestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.catalog.models import Category, Product
from apps.catalog.services import (
    get_category_descendants_dfs,
    get_cached_category_tree,
    invalidate_category_tree_cache,
)

User = get_user_model()

class CategoryDFSTests(TestCase):
    def setUp(self):
        # Clear cache first
        cache.clear()
        
        # Build Category Hierarchy:
        # Electronics (1)
        #  -> Phones (2)
        #      -> iPhones (4)
        #  -> Laptops (3)
        # Clothes (5)
        self.electronics = Category.objects.create(name='Electronics')
        self.phones = Category.objects.create(name='Phones', parent=self.electronics)
        self.laptops = Category.objects.create(name='Laptops', parent=self.electronics)
        self.iphones = Category.objects.create(name='iPhones', parent=self.phones)
        self.clothes = Category.objects.create(name='Clothes')

    def test_dfs_traversal_root(self):
        # DFS from Electronics should yield Electronics, Phones, iPhones, Laptops
        descendants = get_category_descendants_dfs(self.electronics.id)
        expected = {self.electronics.id, self.phones.id, self.iphones.id, self.laptops.id}
        self.assertEqual(set(descendants), expected)

    def test_dfs_traversal_sub(self):
        # DFS from Phones should yield Phones and iPhones
        descendants = get_category_descendants_dfs(self.phones.id)
        expected = {self.phones.id, self.iphones.id}
        self.assertEqual(set(descendants), expected)

    def test_dfs_traversal_leaf(self):
        descendants = get_category_descendants_dfs(self.iphones.id)
        self.assertEqual(descendants, [self.iphones.id])

    def test_caching_and_invalidation(self):
        # First call loads cache
        tree1 = get_cached_category_tree()
        self.assertIsNotNone(cache.get('category_tree'))
        
        # Update category should invalidate cache
        new_cat = Category.objects.create(name='Android Phones', parent=self.phones)
        self.assertIsNone(cache.get('category_tree'))
        
        # Next call should reload cache with new category included
        tree2 = get_cached_category_tree()
        self.assertIn(str(new_cat.id), tree2)


class CatalogAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com', username='admin', password='password123'
        )
        self.regular_user = User.objects.create_user(
            email='user@example.com', username='user', password='password123'
        )
        self.category = Category.objects.create(name='Electronics')
        self.subcategory = Category.objects.create(name='Laptops', parent=self.category)
        
        self.product = Product.objects.create(
            sku='LAP123',
            name='ThinkPad X1',
            price=1500.00,
            stock=10,
            status='active',
            category=self.subcategory
        )
        self.inactive_product = Product.objects.create(
            sku='LAP456',
            name='Old Laptop',
            price=500.00,
            stock=0,
            status='inactive',
            category=self.subcategory
        )

    def test_list_products_public(self):
        url = reverse('product-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only list active products by default for regular public
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['sku'], 'LAP123')

    def test_list_products_category_dfs_filter(self):
        url = reverse('product-list')
        # Filter by Electronics (root category) which has Laptops as subcategory
        response = self.client.get(f"{url}?category_id={self.category.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['sku'], 'LAP123')

    def test_admin_create_product(self):
        url = reverse('product-list')
        token_url = reverse('auth_login')
        login_res = self.client.post(token_url, {'email': 'admin@example.com', 'password': 'password123'})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_res.data['access']}")
        
        new_prod_data = {
            'sku': 'IPHONE15',
            'name': 'iPhone 15',
            'price': 999.00,
            'stock': 20,
            'status': 'active',
            'category_id': self.category.id
        }
        response = self.client.post(url, new_prod_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Product.objects.filter(sku='IPHONE15').exists())

    def test_regular_user_cannot_create_product(self):
        url = reverse('product-list')
        token_url = reverse('auth_login')
        login_res = self.client.post(token_url, {'email': 'user@example.com', 'password': 'password123'})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_res.data['access']}")
        
        new_prod_data = {
            'sku': 'IPHONE15',
            'name': 'iPhone 15',
            'price': 999.00,
            'stock': 20,
            'status': 'active',
            'category_id': self.category.id
        }
        response = self.client.post(url, new_prod_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_recommendations_endpoint(self):
        # Create another product in the same category
        another_prod = Product.objects.create(
            sku='LAP999',
            name='MacBook Air',
            price=1200.00,
            stock=15,
            status='active',
            category=self.subcategory
        )
        url = reverse('product-recommendations', kwargs={'pk': self.product.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should recommend the MacBook Air, and not recommend itself (ThinkPad)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['sku'], 'LAP999')

    def test_category_products_success(self):
        # We query by root category (self.category.id)
        url = reverse('product-category-products', kwargs={'category_id': self.category.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return self.product (since it is in self.subcategory, which is a descendant of self.category)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['sku'], 'LAP123')

    def test_category_products_not_found(self):
        # We query by non-existent category
        url = reverse('product-category-products', kwargs={'category_id': 9999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_category_products_invalid_id(self):
        # We query with an invalid category ID format
        # Since the url regex is `(?P<category_id>[0-9]+)/category`, non-digits won't match the route at all.
        # But we can verify that the endpoint doesn't match and returns 404 Not Found.
        # If we try to hit `/api/products/abc/category/` manually using client:
        response = self.client.get('/api/products/abc/category/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

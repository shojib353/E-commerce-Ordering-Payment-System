from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

class UserModelTests(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='password123'
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.username, 'testuser')
        self.assertTrue(user.check_password('password123'))
        self.assertEqual(str(user), 'test@example.com')

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            email='admin@example.com',
            username='adminuser',
            password='password123'
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class UserAPITests(APITestCase):
    def setUp(self):
        self.register_url = reverse('auth_register')
        self.login_url = reverse('auth_login')
        self.profile_url = reverse('auth_profile')
        self.user_data = {
            'email': 'api_test@example.com',
            'username': 'apitest',
            'password': 'securepassword123',
            'first_name': 'API',
            'last_name': 'Test'
        }

    def test_register_user(self):
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], self.user_data['email'])
        self.assertNotIn('password', response.data)

    def test_login_user(self):
        # Register user first
        self.client.post(self.register_url, self.user_data)
        
        # Login
        login_data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        response = self.client.post(self.login_url, login_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_profile_authenticated(self):
        # Register and login
        self.client.post(self.register_url, self.user_data)
        login_data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        login_res = self.client.post(self.login_url, login_data)
        token = login_res.data['access']
        
        # Access profile
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['email'], self.user_data['email'])
        self.assertEqual(response.data['user']['username'], self.user_data['username'])

    def test_profile_unauthenticated(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

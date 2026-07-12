from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from apps.users.views import UserRegisterView, UserProfileView

urlpatterns = [
    path('register/', UserRegisterView.as_view(), name='auth_register'),
    path('login/', TokenObtainPairView.as_view(), name='auth_login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='auth_token_refresh'),
    path('profile/', UserProfileView.as_view(), name='auth_profile'),
]

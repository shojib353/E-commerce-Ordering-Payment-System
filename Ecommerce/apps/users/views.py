from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from apps.users.serializers import UserRegisterSerializer, UserSerializer
from apps.orders.models import Order

User = get_user_model()

class UserRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]


class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        user_serializer = self.get_serializer(user)
        
        from apps.orders.serializers import OrderSerializer
        orders = Order.objects.filter(user=user).order_by('-created_at')
        orders_serializer = OrderSerializer(orders, many=True)
        
        return Response({
            'user': user_serializer.data,
            'orders': orders_serializer.data
        })

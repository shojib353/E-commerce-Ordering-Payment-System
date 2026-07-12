from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # App routers
    path('api/auth/', include('apps.users.urls')),
    path('api/', include('apps.catalog.urls')),
    path('api/', include('apps.orders.urls')),
    path('api/payments/', include('apps.payments.urls')),
    
    # OpenAPI / Swagger UI / Redoc Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

from django.contrib import admin
from django.urls import path, re_path, include
from django.views.generic import RedirectView

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="Finance APP API",
        default_version='v1',
        description="API documentation for Finance API",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="rdhar8502@gmail.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Redirect root URL to the Swagger UI
    re_path(r'^$', RedirectView.as_view(url='/api/redoc/', permanent=False)),

    path('admin/', admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api/auth/', include('app.urls')),
    path('api/app/', include('fintxnapp.urls')),
]

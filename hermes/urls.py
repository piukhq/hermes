from django.conf.urls import include, url
from django.contrib import admin
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework.permissions import AllowAny

from ubiquity.authentication import ServiceRegistrationAuthentication
from user.authentication import JwtAuthentication

schema_view = get_schema_view(
    openapi.Info(
        title="Ubiquity API",
        default_version='v0.1',
        description="Per me si va nella citta dolente, per me si va nell'eterno dolore, "
                    "per me si va fra la perduta gente.",
    ),
    public=True,
    authentication_classes=(JwtAuthentication, ServiceRegistrationAuthentication),
    permission_classes=(AllowAny,),
)

urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    url(r'^users/', include('user.urls')),
    url(r'^schemes', include('scheme.urls')),
    url(r'^payment_cards', include('payment_card.urls')),
    url(r'^order', include('order.urls')),
    url(r'^ubiquity', include('ubiquity.urls')),
    url(r'', include('common.urls')),
    url(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=None), name='schema-json'),
    url(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=None), name='schema-swagger-ui'),
    url(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=None), name='schema-redoc'),
]

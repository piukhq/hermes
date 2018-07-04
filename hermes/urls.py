
from django.conf.urls import include, url
from django.contrib import admin
from rest_framework_swagger.views import get_swagger_view

urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    url(r'^users/', include('user.urls')),
    url(r'^schemes', include('scheme.urls')),
    url(r'^payment_cards', include('payment_card.urls')),
    url(r'^order', include('order.urls')),
    url(r'', include('common.urls')),
    url(r'^docs/hermes/?', get_swagger_view()),
    url(r'^ubiquity', include('ubiquity.urls')),
]

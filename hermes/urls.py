
from django.conf.urls import include, url
from django.contrib import admin

urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    url(r'^users/', include('user.urls')),
    url(r'^schemes/', include('scheme.urls')),
    url(r'^payment_cards/', include('payment_card.urls')),
]

from django.conf.urls import patterns, url
from order.views import OrderUpdate

urlpatterns = patterns('order',
                       url(r'^$', OrderUpdate.as_view(), name='update_order'),
)

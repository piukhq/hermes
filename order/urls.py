from django.conf.urls import url
from order.views import OrderUpdate

urlpatterns = [
    url(r'^$', OrderUpdate.as_view(), name='update_order'), ]

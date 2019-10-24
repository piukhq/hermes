from django.urls import re_path
from order.views import OrderUpdate

urlpatterns = [re_path(r"^$", OrderUpdate.as_view(), name="update_order")]

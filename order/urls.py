from django.urls import path
from order import views

urlpatterns = [path("", views.OrderUpdate.as_view(), name="update_order")]

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include("user.urls")),
    path("schemes/", include("scheme.urls")),
    path("payment_cards/", include("payment_card.urls")),
    path("order/", include("order.urls")),
    path("ubiquity/", include("ubiquity.urls")),
    path("", include("common.urls")),
]

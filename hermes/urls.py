from django.urls import include, re_path, path
from django.contrib import admin

urlpatterns = [
    path("admin/", admin.site.urls),
    re_path(r"^users/", include("user.urls")),
    re_path(r"^schemes", include("scheme.urls")),
    re_path(r"^payment_cards", include("payment_card.urls")),
    re_path(r"^order", include("order.urls")),
    re_path(r"^ubiquity", include("ubiquity.urls")),
    re_path(r"", include("common.urls")),
]

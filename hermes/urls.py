from django.conf import settings
from django.contrib import admin
from django.urls import include, re_path, path
from django.conf.urls.static import serve

urlpatterns = [
    re_path(r"^admin/oidc/", include("mozilla_django_oidc.urls")),
    re_path(r"^admin/error/", include("sso.urls")),
    path("admin/", admin.site.urls),
    re_path(r"^users/", include("user.urls")),
    re_path(r"^schemes", include("scheme.urls")),
    re_path(r"^payment_cards", include("payment_card.urls")),
    re_path(r"^order", include("order.urls")),
    re_path(r"^ubiquity", include("ubiquity.urls")),
    re_path(r"", include("common.urls")),
    re_path(r'^admin/static/(?P<path>.*)$', serve, kwargs={'document_root': settings.STATIC_ROOT}),
]

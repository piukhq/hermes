from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^healthz$", views.live_z, name="heath_z"),
    re_path(r"^livez$", views.live_z, name="live_z"),
    re_path(r"^readyz$", views.ready_z, name="ready_z"),
]

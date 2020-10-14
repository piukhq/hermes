from django.urls import re_path

from sso import views

urlpatterns = [
    re_path(r"403/?$", views.permission_denied, name="permission_error"),
]

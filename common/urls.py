from django.urls import path

from common import views


urlpatterns = [path("healthz/", views.HealthCheck.as_view())]

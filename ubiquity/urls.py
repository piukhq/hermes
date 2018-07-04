from django.conf.urls import url

from ubiquity.views import ServiceView

urlpatterns = [
    url(r'^/service/?$', ServiceView.as_view(), name='service'),
]

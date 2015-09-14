from django.conf.urls import patterns, url
from user.views import Users

urlpatterns = patterns('user',
                       url(r'^(?P<uid>[\w-]+)/$', Users.as_view(), name='user_detail')
)
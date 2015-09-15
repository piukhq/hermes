from django.conf.urls import patterns, url
from user.views import Users, Register

urlpatterns = patterns('user',
                       url(r'register/$', Register.as_view(), name='user_detail'),
                       url(r'^(?P<uid>[\w-]+)/$', Users.as_view(), name='user_detail'),
)
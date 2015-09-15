from django.conf.urls import patterns, url
from user.views import Users, Register, Login

urlpatterns = patterns('user',
                       url(r'register/$', Register.as_view(), name='user_detail'),
                       url(r'login/$', Login.as_view(), name='user_detail'),
                       url(r'^(?P<uid>[\w-]+)/$', Users.as_view(), name='user_detail'),
)
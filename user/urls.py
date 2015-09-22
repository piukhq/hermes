from django.conf.urls import patterns, url
from user.views import Users, Register, Login, Authenticate, SchemeAccounts

urlpatterns = patterns('user',
                       url(r'authenticate/$', Authenticate.as_view(), name='authenticate_user'),
                       url(r'register/$', Register.as_view(), name='register_user'),
                       url(r'login/$', Login.as_view(), name='login'),
                       url(r'scheme_accounts/$', SchemeAccounts.as_view(), name='user_detail'),
                       url(r'^(?P<uid>[\w-]+)/$', Users.as_view(), name='user_detail'),

)
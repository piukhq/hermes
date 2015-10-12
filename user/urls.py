from django.conf.urls import patterns, url
from user.views import Users, Register, Login, Authenticate, RetrieveSchemeAccount, FaceBookLogin

urlpatterns = patterns('user',
                       url(r'authenticate/?$', Authenticate.as_view(), name='authenticate_user'),
                       url(r'auth/facebook/?$', FaceBookLogin.as_view(), name='authenticate_user'),
                       url(r'register/?$', Register.as_view(), name='register_user'),
                       url(r'login/?$', Login.as_view(), name='login'),
                       url(r'scheme_accounts/(?P<scheme_account_id>[0-9]+)/?$', RetrieveSchemeAccount.as_view(), name='user_detail'),
                       url(r'^(?P<uid>[\w-]+)$', Users.as_view(), name='user_detail'),
)
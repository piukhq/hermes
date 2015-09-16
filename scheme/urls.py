from django.conf.urls import patterns, url
from scheme.views import CreateAccount, Schemes, EditAccount

urlpatterns = patterns('scheme',
                       url(r'account/$', CreateAccount.as_view(), name='create_scheme_account'),
                       url(r'account/(?P<pk>[0-9]+)$', EditAccount.as_view(), name='create_scheme_account'),
                       url(r'list/$', Schemes.as_view(), name='list_schemes'),
)

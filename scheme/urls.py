from django.conf.urls import patterns, url
from scheme.views import (CreateAccount, SchemesList, RetrieveUpdateDeleteAccount, RetrieveScheme,
                            CreateAnswer, RetrieveUpdateDestroyAnswer)

urlpatterns = patterns('schemes',
                       url(r'accounts/?$', CreateAccount.as_view(), name='create_scheme_account'),
                       url(r'accounts/(?P<pk>[0-9]+)$', RetrieveUpdateDeleteAccount.as_view(), name='retrieve_account'),
                       url(r'^$', SchemesList.as_view(), name='list_schemes'),
                       url(r'^(?P<pk>[0-9]+)$', RetrieveScheme.as_view(), name='retrieve_scheme'),
                       url(r'^accounts/credentials', CreateAnswer.as_view(), name='create_question'),
)

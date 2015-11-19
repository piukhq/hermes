from django.conf.urls import patterns, url
from scheme.views import (CreateAccount, SchemesList, RetrieveDeleteAccount, RetrieveScheme,
                          LinkCredentials, SchemeAccountsCredentials, UpdateSchemeAccountStatus,
                          ActiveSchemeAccountAccounts, SystemActionSchemeAccounts, SchemeAccountStatusData)

urlpatterns = patterns('schemes',
                       url(r'^/accounts/?$', CreateAccount.as_view(), name='create_scheme_account'),
                       url(r'^/accounts/active$', ActiveSchemeAccountAccounts.as_view(), name='create_scheme_account'),
                       url(r'^/accounts/system_retry$', SystemActionSchemeAccounts.as_view(),
                           name='create_scheme_account'),
                       url(r'^/accounts/(?P<pk>[0-9]+)/service_credentials', SchemeAccountsCredentials.as_view(),
                           name='change_account_status'),
                       url(r'^/accounts/(?P<pk>[0-9]+)/status/?$', UpdateSchemeAccountStatus.as_view(),
                           name='change_account_status'),
                       url(r'^/accounts/(?P<pk>[0-9]+)$', RetrieveDeleteAccount.as_view(),
                           name='retrieve_account'),
                       url(r'^/?$', SchemesList.as_view(), name='list_schemes'),
                       url(r'^/(?P<pk>[0-9]+)$', RetrieveScheme.as_view(), name='retrieve_scheme'),
                       url(r'^/accounts/(?P<pk>[0-9]+)/link', LinkCredentials.as_view(), name='create_question'),
                       url(r'^/accounts/summary', SchemeAccountStatusData.as_view(), name='schemes_status_summary'),)

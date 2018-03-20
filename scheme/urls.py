from django.conf.urls import url
from scheme import views

urlpatterns = [
    url(r'^/accounts/?$',
        views.CreateAccount.as_view(),
        name='create_scheme_account'),

    url(r'^/accounts/my360/?$',
        views.CreateMy360AccountsAndLink.as_view(),
        name='create_my360_accounts_and_link'),

    url(r'^/accounts/query$',
        views.SchemeAccountQuery.as_view(),
        name='query_scheme_accounts'),

    url(r'^/accounts/active$',
        views.ActiveSchemeAccountAccounts.as_view(),
        name='create_scheme_account'),

    url(r'^/accounts/system_retry$',
        views.SystemActionSchemeAccounts.as_view(),
        name='create_scheme_account'),

    url(r'^/accounts/(?P<pk>[0-9]+)/credentials',
        views.SchemeAccountsCredentials.as_view(),
        name='change_account_status'),

    url(r'^/accounts/(?P<pk>[0-9]+)/status/?$',
        views.UpdateSchemeAccountStatus.as_view(),
        name='change_account_status'),

    url(r'^/accounts/(?P<pk>[0-9]+)$',
        views.RetrieveDeleteAccount.as_view(),
        name='retrieve_account'),

    url(r'^/accounts/donor_schemes/(?P<scheme_id>[0-9]+)/(?P<user_id>[0-9]+)/?$',
        views.DonorSchemes.as_view()),

    url(r'^/accounts/join/(?P<scheme_slug>[a-z0-9\-]+)/(?P<user_id>[0-9]+)/?$',
        views.CreateJoinSchemeAccount.as_view()),

    url(r'^/?$',
        views.SchemesList.as_view(),
        name='list_schemes'),

    url(r'^/(?P<pk>[0-9]+)$',
        views.RetrieveScheme.as_view(),
        name='retrieve_scheme'),

    url(r'^/accounts/(?P<pk>[0-9]+)/link',
        views.LinkCredentials.as_view(),
        name='create_question'),

    url(r'^/accounts/summary',
        views.SchemeAccountStatusData.as_view(),
        name='schemes_status_summary'),

    url(r'^/images/reference',
        views.ReferenceImages.as_view()),

    url(r'^/identify',
        views.IdentifyCard.as_view()),

    # TODO: Better URL
    url(r'^/csv_upload',
        views.csv_upload, name='csv_upload'),

    url(r'^/(?P<pk>[0-9]+)/join',
        views.Join.as_view(),
        name='create_join_scheme_account'),
]

from django.urls import re_path

from scheme import views

urlpatterns = [
    re_path(
        r"^/accounts/?$", views.CreateAccount.as_view(),
        name="create_scheme_account"),
    re_path(
        r"^/accounts/query$", views.SchemeAccountQuery.as_view(),
        name="query_scheme_accounts"),
    re_path(
        r"^/accounts/active$", views.ActiveSchemeAccountAccounts.as_view(),
        name="create_scheme_account"),
    re_path(
        r"^/accounts/system_retry$", views.SystemActionSchemeAccounts.as_view(),
        name="create_scheme_account"),
    re_path(
        r"^/accounts/(?P<pk>[0-9]+)/credentials", views.SchemeAccountsCredentials.as_view(),
        name="change_account_credentials",
    ),
    re_path(
        r"^/accounts/(?P<pk>[0-9]+)/status/?$", views.UpdateSchemeAccountStatus.as_view(),
        name="change_account_status"
    ),
    re_path(
        r"^/accounts/(?P<pk>[0-9]+)/transactions/?$", views.UpdateSchemeAccountTransactions.as_view(),
        name="update_account_transactions"
    ),
    re_path(
        r"^/accounts/(?P<pk>[0-9]+)$", views.RetrieveDeleteAccount.as_view(),
        name="retrieve_account"
    ),
    re_path(
        r"^/accounts/(?P<pk>[0-9]+)/service/?$", views.ServiceDeleteAccount.as_view(),
        name="service_delete_account"
    ),
    re_path(
        r"^/accounts/donor_schemes/(?P<scheme_id>[0-9]+)/(?P<user_id>[0-9]+)/?$", views.DonorSchemes.as_view()
    ),
    re_path(
        r"^/accounts/join/(?P<scheme_slug>[a-z0-9\-]+)/(?P<user_id>[0-9]+)/?$", views.CreateJoinSchemeAccount.as_view()
    ),
    re_path(
        r"^/?$", views.SchemesList.as_view(),
        name="list_schemes"
    ),
    re_path(
        r"^/(?P<pk>[0-9]+)$", views.RetrieveScheme.as_view(),
        name="retrieve_scheme"
    ),
    # re_path(
    #     r"^/accounts/(?P<pk>[0-9]+)/link", views.LinkCredentials.as_view(),
    #     name="create_question"
    # ),
    re_path(
        r"^/user_consent/(?P<pk>[0-9]+)$", views.UpdateUserConsent.as_view(),
        name="update_user_consent"
    ),
    re_path(
        r"^/accounts/summary", views.SchemeAccountStatusData.as_view(),
        name="schemes_status_summary"
    ),
    re_path(
        r"^/images/reference", views.ReferenceImages.as_view()
    ),
    re_path(
        r"^/identify", views.IdentifyCard.as_view()
    ),
    re_path(
        r"^/csv_upload", views.csv_upload,
        name="csv_upload"
    ),
    re_path(
        r"^/(?P<pk>[0-9]+)/join", views.Join.as_view(),
        name="create_join_scheme_account"
    ),
]

from django.urls import path

from scheme import views

urlpatterns = [
    path("accounts/", views.CreateAccount.as_view(), name="create_scheme_account"),
    path("accounts/query/", views.SchemeAccountQuery.as_view(), name="query_scheme_accounts"),
    path("accounts/active/", views.ActiveSchemeAccountAccounts.as_view(), name="create_scheme_account"),
    path("accounts/system_retry/", views.SystemActionSchemeAccounts.as_view(), name="create_scheme_account"),
    path(
        "accounts/<int:pk>/credentials/", views.SchemeAccountsCredentials.as_view(), name="change_account_credentials"
    ),
    path("accounts/<int:pk>/status/", views.UpdateSchemeAccountStatus.as_view(), name="change_account_status"),
    path("accounts/<int:pk>/", views.RetrieveDeleteAccount.as_view(), name="retrieve_account"),
    path("accounts/<int:pk>/service/", views.ServiceDeleteAccount.as_view(), name="service_delete_account"),
    path("accounts/donor_schemes/<int:scheme_id>/<int:user_id>/", views.DonorSchemes.as_view()),
    path("accounts/join/<slug:scheme_slug>/<int:user_id>/", views.CreateJoinSchemeAccount.as_view()),
    path("/", views.SchemesList.as_view(), name="list_schemes"),
    path("<int:pk>/", views.RetrieveScheme.as_view(), name="retrieve_scheme"),
    path("accounts/<int:pk>/link/", views.LinkCredentials.as_view(), name="create_question"),
    path("user_consent/<int:pk>/", views.UpdateUserConsent.as_view(), name="update_user_consent"),
    path("accounts/summary/", views.SchemeAccountStatusData.as_view(), name="schemes_status_summary"),
    path("images/reference/", views.ReferenceImages.as_view()),
    path("identify/", views.IdentifyCard.as_view()),
    path("csv_upload/", views.csv_upload, name="csv_upload"),
    path("<int:pk>/join/", views.Join.as_view(), name="create_join_scheme_account"),
]

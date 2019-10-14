from django.urls import path

from payment_card import views

urlpatterns = [
    path("/", views.ListPaymentCard.as_view(), name="payment_card_list"),
    path("accounts/query/", views.PaymentCardAccountQuery.as_view(), name="query_payment_card_accounts"),
    path("accounts/", views.ListCreatePaymentCardAccount.as_view(), name="create_payment_card_account"),
    path("accounts/loyalty_id/<slug:scheme_slug>/", views.RetrieveLoyaltyID.as_view(), name="retrieve_loyalty_ids"),
    path(
        "accounts/payment_card_user_info/<slug:scheme_slug>/",
        views.RetrievePaymentCardUserInfo.as_view(),
        name="retrieve_payment_card_user_info",
    ),
    path("accounts/<int:pk>/", views.RetrievePaymentCardAccount.as_view(), name="retrieve_payment_card_account"),
    path(
        "scheme_accounts/<str:token>/",
        views.RetrievePaymentCardSchemeAccounts.as_view(),
        name="retrieve_payment_card_scheme_accounts",
    ),
    path("accounts/status/", views.UpdatePaymentCardAccountStatus.as_view(), name="update_payment_card_account_status"),
    path(
        "provider_status_mappings/<slug:slug>/",
        views.ListProviderStatusMappings.as_view(),
        name="list_provider_status_mappings",
    ),
    path("csv_upload/", views.csv_upload, name="csv_upload"),
    path("auth_transaction/", views.AuthTransactionView.as_view(), name="auth_transaction"),
    path("client_apps/", views.ListPaymentCardClientApplication.as_view(), name="list_payment_card_client_apps"),
]

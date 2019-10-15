from django.urls import re_path

from payment_card import views

urlpatterns = [
    re_path(r"^/?$", views.ListPaymentCard.as_view(), name="payment_card_list"),
    re_path(r"^/accounts/query$", views.PaymentCardAccountQuery.as_view(), name="query_payment_card_accounts"),
    re_path(r"^/accounts$", views.ListCreatePaymentCardAccount.as_view(), name="create_payment_card_account"),
    re_path(
        r"^/accounts/loyalty_id/(?P<scheme_slug>.+)$", views.RetrieveLoyaltyID.as_view(), name="retrieve_loyalty_ids"
    ),
    re_path(
        r"^/accounts/payment_card_user_info/(?P<scheme_slug>.+)$",
        views.RetrievePaymentCardUserInfo.as_view(),
        name="retrieve_payment_card_user_info",
    ),
    re_path(
        r"^/accounts/(?P<pk>[0-9]+)$", views.RetrievePaymentCardAccount.as_view(), name="retrieve_payment_card_account"
    ),
    re_path(
        r"^/scheme_accounts/(?P<token>.+)$",
        views.RetrievePaymentCardSchemeAccounts.as_view(),
        name="retrieve_payment_card_scheme_accounts",
    ),
    re_path(
        r"^/accounts/status$", views.UpdatePaymentCardAccountStatus.as_view(), name="update_payment_card_account_status"
    ),
    re_path(
        r"^/provider_status_mappings/(?P<slug>.+)$",
        views.ListProviderStatusMappings.as_view(),
        name="list_provider_status_mappings",
    ),
    re_path(r"^/csv_upload", views.csv_upload, name="csv_upload"),
    re_path(r"^/auth_transaction$", views.AuthTransactionView.as_view(), name="auth_transaction"),
    re_path(r"^/client_apps$", views.ListPaymentCardClientApplication.as_view(), name="list_payment_card_client_apps"),
]

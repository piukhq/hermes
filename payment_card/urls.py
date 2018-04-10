from django.conf.urls import url

from payment_card import views

urlpatterns = [
    url(r'^/?$',
        views.ListPaymentCard.as_view(),
        name='payment_card_list'),

    url(r'^/accounts/query$',
        views.PaymentCardAccountQuery.as_view(),
        name='query_payment_card_accounts'),

    url(r'^/accounts$',
        views.ListCreatePaymentCardAccount.as_view(),
        name='create_payment_card_account'),

    url(r'^/accounts/loyalty_id/(?P<scheme_slug>.+)$',
        views.RetrieveLoyaltyID.as_view(),
        name='retrieve_loyalty_ids'),

    url(r'^/accounts/payment_card_user_info/(?P<scheme_slug>.+)$',
        views.RetrievePaymentCardUserInfo.as_view(),
        name='retrieve_payment_card_user_info'),

    url(r'^/accounts/(?P<pk>[0-9]+)$',
        views.RetrievePaymentCardAccount.as_view(),
        name='retrieve_payment_card_account'),

    url(r'^/scheme_accounts/(?P<token>.+)$',
        views.RetrievePaymentCardSchemeAccounts.as_view(),
        name='retrieve_payment_card_scheme_accounts'),

    url(r'^/accounts/status$',
        views.UpdatePaymentCardAccountStatus.as_view(),
        name='update_payment_card_account_status'),

    url(r'^/provider_status_mappings/(?P<slug>.+)$',
        views.ListProviderStatusMappings.as_view(),
        name='list_provider_status_mappings'),

    # TODO: Better URL
    url(r'^/csv_upload', views.csv_upload, name='csv_upload'), ]


for slug, view_args in views.auth_transaction_views.items():
    urlpatterns.append(url(
        r'^/auth_transaction/{}$'.format(slug),
        views.generics.CreateAPIView.as_view(**view_args),
        name='create_auth_transaction_{}'.format(slug)))

from django.conf.urls import patterns, url
from payment_card.views import RetrievePaymentCardAccount, RetrievePaymentCardSchemeAccounts,\
    ListPaymentCard, ListCreatePaymentCardAccount, RetrieveLoyaltyID, RetrievePaymentCardUserInfo, csv_upload

urlpatterns = patterns('payment_card',
                       url(r'^/?$', ListPaymentCard.as_view(), name='payment_card_list'),
                       url(r'^/accounts$', ListCreatePaymentCardAccount.as_view(),
                           name='create_payment_card_account'),
                       url(r'^/accounts/loyalty_id/(?P<scheme_slug>.+)$',  RetrieveLoyaltyID.as_view(),
                           name='retrieve_loyalty_ids'),
                       url(r'^/accounts/payment_card_user_info/(?P<scheme_slug>.+)$',
                           RetrievePaymentCardUserInfo.as_view(),
                           name='retrieve_payment_card_user_info'),
                       url(r'^/accounts/(?P<pk>[0-9]+)$', RetrievePaymentCardAccount.as_view(),
                           name='retrieve_payment_card_account'),
                       url(r'^/scheme_accounts/(?P<token>.+)$', RetrievePaymentCardSchemeAccounts.as_view(),
                           name='retrieve_payment_card_scheme_accounts'),
                       # TODO: Better URL
                       url(r'^/csv_upload', csv_upload, name='csv_upload'),
                       )

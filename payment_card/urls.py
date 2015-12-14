from django.conf.urls import patterns, url
from payment_card.views import RetrievePaymentCardAccount, RetrievePaymentCardSchemeAccounts,\
    ListPaymentCard, CreatePaymentCardAccount

urlpatterns = patterns('payment_card',
                       url(r'^/?$', ListPaymentCard.as_view(), name='payment_card_list'),
                       url(r'^/accounts$', CreatePaymentCardAccount.as_view(),
                           name='create_payment_card_account'),
                       url(r'^/accounts/(?P<pk>[0-9]+)$', RetrievePaymentCardAccount.as_view(),
                           name='retrieve_payment_card_account'),
                       url(r'^/scheme_accounts/(?P<token>.+)$', RetrievePaymentCardSchemeAccounts.as_view(),
                           name='retrieve_payment_card_scheme_accounts'),
                       )

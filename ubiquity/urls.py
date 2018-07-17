from django.conf.urls import url

from ubiquity.views import (CreateDeleteLinkView, LinkMembershipCardView, ListPaymentCardView,
                            MembershipCardTransactionsView, MembershipCardView, PaymentCardView, ServiceView,
                            TestBalance, UserTransactions)

urlpatterns = [
    url(r'^/service/?$', ServiceView.as_view(), name='service'),
    url(r'^/payment_cards/?$', ListPaymentCardView.as_view(), name='payment-cards'),
    url(r'^/payment_card/(?P<pk>[0-9]+)?$', PaymentCardView.as_view(), name='payment-card'),
    url(r'^/membership_cards/?$', LinkMembershipCardView.as_view(), name='membership-cards'),
    url(r'^/membership_card/(?P<pk>[0-9]+)?$', MembershipCardView.as_view(), name='membership-card'),
    url(r'^/get_balance/?$', TestBalance.as_view(), name='get-balance'),
    url(r'^/link/payment_card/(?P<pcard_id>[0-9]+)/membership_card/(?P<mcard_id>[0-9]+)$',
        CreateDeleteLinkView.as_view(), name='link-create-delete'),
    url(r'^/transactions/?$', UserTransactions.as_view(), name='user-transactions'),
    url(r'^/membership_card?/(?P<mcard_id>[0-9]+)/transactions$', MembershipCardTransactionsView.as_view(),
        name='get-transactions'),

]

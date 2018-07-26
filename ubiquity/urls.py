from django.conf.urls import url

from scheme.views import RetrieveScheme, SchemesList
from ubiquity.views import (CreateDeleteLinkView, LinkMembershipCardView, ListPaymentCardView,
                            MembershipCardTransactionsView, MembershipCardView, PaymentCardView, ServiceView,
                            TestBalance, UserTransactions, CompositeMembershipCardView, CompositePaymentCardView)

cards_plural = {'get': 'list', 'post': 'create'}
cards_single = {'get': 'retrieve', 'delete': 'destroy'}


urlpatterns = [
    url(r'^/service/?$', ServiceView.as_view(), name='service'),
    url(r'^/payment_cards/?$', ListPaymentCardView.as_view(cards_plural), name='payment-cards'),
    url(r'^/payment_card/(?P<pk>[0-9]+)?$', PaymentCardView.as_view(cards_single), name='payment-card'),
    url(r'^/membership_cards/?$', LinkMembershipCardView.as_view(cards_plural), name='membership-cards'),
    url(r'^/membership_card/(?P<pk>[0-9]+)?$', MembershipCardView.as_view(cards_single), name='membership-card'),
    url(r'^/get_balance/?$', TestBalance.as_view(), name='get-balance'),
    url(r'^/link/payment_card/(?P<pcard_id>[0-9]+)/membership_card/(?P<mcard_id>[0-9]+)$',
        CreateDeleteLinkView.as_view(), name='link-create-delete'),
    url(r'^/transactions/?$', UserTransactions.as_view(), name='user-transactions'),
    url(r'^/membership_card?/(?P<mcard_id>[0-9]+)/transactions$', MembershipCardTransactionsView.as_view(),
        name='get-transactions'),
    url(r'^/membership_plans/?$', SchemesList.as_view(), name='list_plans'),
    url(r'^/membership_plan/(?P<pk>[0-9]+)$', RetrieveScheme.as_view(), name='get_plan'),
    # url(r'^/payment_card/(?P<pcard_id>\d+)/membership_cards/?$',
    #     CompositeMembershipCardView.as_view(), name='get_create_composite_mcards'),
    # url(r'^/membership_card/(?P<mcard_id>\d+)/payment_cards/?$',
    #     CompositePaymentCardView.as_view(), name='get_create_composite_pcards'),

]

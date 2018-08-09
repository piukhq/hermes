from django.conf.urls import url

from scheme.views import RetrieveScheme
from ubiquity.views import (CompositeMembershipCardView, CompositePaymentCardView, CreateDeleteLinkView,
                            ListMembershipCardView, ListPaymentCardView, MembershipCardView, MembershipPlans,
                            PaymentCardView, ServiceView, UserTransactions, MembershipPlan)

service_view = {'get': 'retrieve', 'post': 'create', 'delete': 'destroy'}
cards_plural = {'get': 'list', 'post': 'create'}
cards_singular = {'get': 'retrieve', 'delete': 'destroy', 'patch': 'patch'}
link_payment = {'patch': 'update_payment', 'delete': 'destroy_payment'}
link_membership = {'patch': 'update_membership', 'delete': 'destroy_membership'}

urlpatterns = [
    url(r'^/service/?$',
        ServiceView.as_view(service_view), name='service'),
    url(r'^/payment_cards/?$',
        ListPaymentCardView.as_view(cards_plural), name='payment-cards'),
    url(r'^/payment_card/(?P<pk>[0-9]+)?$',
        PaymentCardView.as_view(cards_singular), name='payment-card'),
    url(r'^/membership_cards/?$',
        ListMembershipCardView.as_view(cards_plural), name='membership-cards'),
    url(r'^/membership_card/(?P<pk>[0-9]+)?$',
        MembershipCardView.as_view(cards_singular), name='membership-card'),
    url(r'^/transactions/?$',
        UserTransactions.as_view({'get': 'list'}), name='user-transactions'),
    url(r'^/membership_card?/(?P<mcard_id>[0-9]+)/transactions$',
        MembershipCardView.as_view({'get': 'transactions'}),
        name='membership-card-transactions'),
    url(r'^/membership_plans/?$',
        MembershipPlans.as_view({'get': 'list'}), name='membership-plans'),
    url(r'^/membership_plan/(?P<pk>[0-9]+)$',
        MembershipPlan.as_view({'get': 'retrieve'}), name='membership-plan'),
    url(r'^/payment_card/(?P<pcard_id>\d+)/membership_cards/?$',
        CompositeMembershipCardView.as_view(cards_plural), name='composite-membership-cards'),
    url(r'^/membership_card/(?P<mcard_id>\d+)/payment_cards/?$',
        CompositePaymentCardView.as_view(cards_plural), name='composite-payment-cards'),
    url(r'^/payment_card/(?P<pcard_id>[0-9]+)/membership_card/(?P<mcard_id>[0-9]+)/?$',
        CreateDeleteLinkView.as_view(link_membership), name='membership-link'),
    url(r'^/membership_card/(?P<mcard_id>[0-9]+)/payment_card/(?P<pcard_id>[0-9]+)/?$',
        CreateDeleteLinkView.as_view(link_payment), name='payment-link'),
]

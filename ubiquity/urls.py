from django.conf.urls import url

from ubiquity.views import (LinkMembershipCardView, ListPaymentCardView, MembershipCardView, PaymentCardView,
                            ServiceView, TestBalance)

urlpatterns = [
    url(r'^/service/?$', ServiceView.as_view(), name='service'),
    url(r'^/payment_cards/?$', ListPaymentCardView.as_view(), name='payment_cards'),
    url(r'^/payment_card/(?P<pk>[0-9]+)?$', PaymentCardView.as_view(), name='payment_card'),
    url(r'^/membership_cards/?$', LinkMembershipCardView.as_view(), name='membership_cards'),
    url(r'^/membership_card/(?P<pk>[0-9]+)?$', MembershipCardView.as_view(), name='membership_card'),
    url(r'^/get_balance/?$', TestBalance.as_view(), name='get_balance'),
]

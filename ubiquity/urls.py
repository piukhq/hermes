from django.urls import re_path

from ubiquity.views import (
    CompositeMembershipCardView,
    CompositePaymentCardView,
    CardLinkView,
    ListMembershipCardView,
    ListPaymentCardView,
    MembershipCardView,
    MembershipPlanView,
    ListMembershipPlanView,
    MembershipTransactionView,
    PaymentCardView,
    ServiceView,
)

service_view = {"get": "retrieve", "post": "create", "delete": "destroy"}
cards_plural = {"get": "list", "post": "create"}
cards_singular = {"get": "retrieve", "delete": "destroy", "patch": "update", "put": "replace"}
link_payment = {"patch": "update_payment", "delete": "destroy_payment"}
link_membership = {"patch": "update_membership", "delete": "destroy_membership"}
delete_only = {"delete": "destroy"}

urlpatterns = [
    re_path(
        r"^/service/?$",
        ServiceView.as_view(service_view),
        name="service"
    ),
    re_path(
        r"^/payment_cards/?$",
        ListPaymentCardView.as_view(cards_plural),
        name="payment-cards"
    ),
    re_path(
        r"^/payment_card/(?P<pk>[0-9]+)/?$",
        PaymentCardView.as_view(cards_singular),
        name="payment-card"
    ),
    re_path(
        r"^/payment_card/id-(?P<pk>[0-9]+)/?$",
        PaymentCardView.as_view(delete_only),
        name="payment-card-id"
    ),
    re_path(
        r"^/payment_card/hash-(?P<hash>\w+)/?$",
        PaymentCardView.as_view(delete_only, lookup_field='hash'),
        name="payment-card-hash"
    ),
    re_path(
        r"^/membership_cards/?$",
        ListMembershipCardView.as_view(cards_plural),
        name="membership-cards"
    ),
    re_path(
        r"^/membership_card/(?P<pk>[0-9]+)?$",
        MembershipCardView.as_view(cards_singular),
        name="membership-card"
    ),
    re_path(
        r"^/membership_transactions/?$",
        MembershipTransactionView.as_view({"get": "list"}),
        name="user-transactions"
    ),
    re_path(
        r"^/membership_transaction/(?P<transaction_id>[0-9]+)?$",
        MembershipTransactionView.as_view({"get": "retrieve"}),
        name="retrieve-transactions",
    ),
    re_path(
        r"^/membership_card?/(?P<mcard_id>[0-9]+)/membership_transactions$",
        MembershipTransactionView.as_view({"get": "composite"}),
        name="membership-card-transactions",
    ),
    re_path(
        r"^/membership_card?/(?P<mcard_id>[0-9]+)/membership_plan$",
        MembershipCardView.as_view({"get": "membership_plan"}),
        name="membership-card-plan",
    ),
    re_path(
        r"^/membership_plans/?$",
        ListMembershipPlanView.as_view({"get": "list", "post": "identify"}),
        name="membership-plans",
    ),
    re_path(
        r"^/membership_plan/(?P<pk>[0-9]+)$",
        MembershipPlanView.as_view({"get": "retrieve"}),
        name="membership-plan"
    ),
    re_path(
        r"^/payment_card/(?P<pcard_id>\d+)/membership_cards/?$",
        CompositeMembershipCardView.as_view(cards_plural),
        name="composite-membership-cards",
    ),
    re_path(
        r"^/membership_card/(?P<mcard_id>\d+)/payment_cards/?$",
        CompositePaymentCardView.as_view(cards_plural),
        name="composite-payment-cards",
    ),
    re_path(
        r"^/payment_card/(?P<pcard_id>[0-9]+)/membership_card/(?P<mcard_id>[0-9]+)/?$",
        CardLinkView.as_view(link_membership),
        name="membership-link",
    ),
    re_path(
        r"^/membership_card/(?P<mcard_id>[0-9]+)/payment_card/(?P<pcard_id>[0-9]+)/?$",
        CardLinkView.as_view(link_payment),
        name="payment-link",
    ),
]

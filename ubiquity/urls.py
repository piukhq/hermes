from django.urls import path

from ubiquity import views

service_view = {"get": "retrieve", "post": "create", "delete": "destroy"}
cards_plural = {"get": "list", "post": "create"}
cards_singular = {"get": "retrieve", "delete": "destroy", "patch": "update", "put": "replace"}
link_payment = {"patch": "update_payment", "delete": "destroy_payment"}
link_membership = {"patch": "update_membership", "delete": "destroy_membership"}

urlpatterns = [
    path("service/", views.ServiceView.as_view(service_view), name="service"),
    path("payment_cards/", views.ListPaymentCardView.as_view(cards_plural), name="payment-cards"),
    path("payment_card/<int:pk>/", views.PaymentCardView.as_view(cards_singular), name="payment-card"),
    path("membership_cards/", views.ListMembershipCardView.as_view(cards_plural), name="membership-cards"),
    path("membership_card/<int:pk>/", views.MembershipCardView.as_view(cards_singular), name="membership-card"),
    path(
        "membership_transactions/", views.MembershipTransactionView.as_view({"get": "list"}), name="user-transactions"
    ),
    path(
        "membership_transaction/<int:transaction_id>/",
        views.MembershipTransactionView.as_view({"get": "retrieve"}),
        name="retrieve-transactions",
    ),
    path(
        "membership_card/<int:mcard_id>/membership_transactions/",
        views.MembershipTransactionView.as_view({"get": "composite"}),
        name="membership-card-transactions",
    ),
    path(
        "membership_card/<int:mcard_id>/membership_plan/",
        views.MembershipCardView.as_view({"get": "membership_plan"}),
        name="membership-card-plan",
    ),
    path(
        "membership_plans/",
        views.ListMembershipPlanView.as_view({"get": "list", "post": "identify"}),
        name="membership-plans",
    ),
    path("membership_plan/<int:pk>/", views.MembershipPlanView.as_view({"get": "retrieve"}), name="membership-plan"),
    path(
        "payment_card/<int:pcard_id>/membership_cards/",
        views.CompositeMembershipCardView.as_view(cards_plural),
        name="composite-membership-cards",
    ),
    path(
        "membership_card/<int:mcard_id>/payment_cards/",
        views.CompositePaymentCardView.as_view(cards_plural),
        name="composite-payment-cards",
    ),
    path(
        "payment_card/<int:pcard_id>/membership_card/<int:mcard_id>/",
        views.CardLinkView.as_view(link_membership),
        name="membership-link",
    ),
    path(
        "membership_card/<int:mcard_id>/payment_card/<int:pcard_id>/",
        views.CardLinkView.as_view(link_payment),
        name="payment-link",
    ),
]

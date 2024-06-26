from enum import Enum

from django_prometheus.conf import NAMESPACE
from django_prometheus.middleware import Metrics
from prometheus_client import Counter, Histogram


def m(metric_name: str) -> str:
    return f"django_http_{metric_name}"


ADD_CHANNEL_TO_METRICS = [
    m("requests_latency_seconds_by_view_method"),
    m("responses_total_by_status_view_method"),
]


class PaymentCardAddRoute(str, Enum):
    NEW_CARD = "New Card"
    MULTI_WALLET = "Multi Wallet"
    RETURNING = "Returning"


class MembershipCardAddRoute(str, Enum):
    LINK = "Link"
    ENROL = "Enrol"
    REGISTER = "Register"
    UPDATE = "Update"
    WALLET_ONLY = "Wallet Only"
    MULTI_WALLET = "Multi Wallet"


class CustomMetrics(Metrics):
    def register_metric(self, metric_cls, name, documentation, labelnames=(), **kwargs):
        if name in ADD_CHANNEL_TO_METRICS:
            labelnames += ("channel",)

        return super().register_metric(metric_cls, name, documentation, labelnames=labelnames, **kwargs)


# declare here custom labels to be used directly
service_creation_counter = Counter(
    name="service_creation_total",
    documentation="Number of total services registered.",
    labelnames=("channel",),
    namespace=NAMESPACE,
)

payment_card_add_counter = Counter(
    name="payment_card_add_total",
    documentation="Total number of payment cards added.",
    labelnames=("channel", "provider", "route"),
    namespace=NAMESPACE,
)

payment_card_status_change_counter = Counter(
    name="payment_card_status_change_total",
    documentation="Total number of payment card status changes.",
    labelnames=("provider", "status"),
    namespace=NAMESPACE,
)

payment_card_processing_seconds_histogram = Histogram(
    name="payment_card_processing_seconds_histogram",
    documentation="Processing time for payment cards.",
    labelnames=("provider",),
    buckets=(5.0, 10.0, 30.0, 300.0, 3600.0, 43200.0, 86400.0, float("inf")),
    namespace=NAMESPACE,
)

membership_card_add_counter = Counter(
    name="membership_card_add_total",
    documentation="Total number of membership cards added.",
    labelnames=("channel", "scheme", "route"),
    namespace=NAMESPACE,
)

membership_card_update_counter = Counter(
    name="membership_card_update_total",
    documentation="Total number of membership cards updated.",
    labelnames=("channel", "scheme", "route"),
    namespace=NAMESPACE,
)

membership_card_status_change_counter = Counter(
    name="membership_card_status_change_total",
    documentation="Total number of membership cards status changes.",
    labelnames=("channel", "scheme", "status_change"),
    namespace=NAMESPACE,
)

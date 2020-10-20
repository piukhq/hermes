from enum import Enum

from django_prometheus.conf import NAMESPACE
from django_prometheus.middleware import Metrics
from prometheus_client import Counter


def m(metric_name: str) -> str:
    return f"django_http_{metric_name}"


ADD_CHANNEL_TO_METRICS = [
    m("requests_latency_seconds_by_view_method"),
]


class PaymentCardAddRoute(str, Enum):
    NEW_CARD = "New Card"
    MULTI_WALLET = "Multi Wallet"
    RETURNING = "Returning"


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

payment_card_status_counter = Counter(
    name='payment_card_status_total',
    documentation='Total number of payment card status changes.',
    labelnames=("scheme", "status"),
    namespace=NAMESPACE,
)

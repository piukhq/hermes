from enum import Enum

from django_prometheus.conf import NAMESPACE
from django_prometheus.middleware import Metrics
from prometheus_client import Counter

from django.conf import settings


class PaymentCardAddRoute(str, Enum):
    NEW_CARD = "new"
    MULTI_WALLET = "multi"
    RETURNING = "returning"


class CustomMetrics(Metrics):
    def register_metric(self, metric_cls, name, documentation, labelnames=(), **kwargs):
        if name in settings.ADD_CHANNEL_LABEL_TO_METRICS:
            labelnames += ("channel",)

        return super().register_metric(metric_cls, name, documentation, labelnames=labelnames, **kwargs)


# declare here custom labels to be used directly
service_creation_total = Counter(
    name="service_creation_total",
    documentation="Number of total services registered.",
    labelnames=("channel",),
    namespace=NAMESPACE,
)

payment_card_add_total = Counter(
    name="payment_card_add_total",
    documentation="Total number of payment cards added.",
    labelnames=("channel", "provider", "route"),
    namespace=NAMESPACE,
)

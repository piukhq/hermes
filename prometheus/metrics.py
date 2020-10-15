from enum import Enum

from django_prometheus.conf import NAMESPACE
from django_prometheus.middleware import Metrics
from prometheus_client import Counter


class PaymentCardAddRoute(str, Enum):
    NEW_CARD = "new"
    MULTI_WALLET = "multi"
    RETURNING = "returning"


class CustomMetrics(Metrics):

    # noinspection PyAttributeOutsideInit
    def register(self):
        super(CustomMetrics, self).register()
        # ------------------------- declare here custom labels to be used in the middleware ------------------------- #
        self.requests_by_method_channel_view_and_response_status = self.register_metric(
            Counter,
            "django_http_requests_total_by_method_channel_view_and_response_status",
            "Count of requests by method, channel, view, and response status",
            ["method", "channel", "view", "response_status"],
            namespace=NAMESPACE,
        )
        # ----------------------------------------------------------------------------------------------------------- #


# declare here custom labels to be used directly
service_creation_total = Counter(
    name="service_creation_total",
    documentation="Number of total services registered.",
    labelnames=("channel",),
    namespace=NAMESPACE
)

payment_card_add_total = Counter(
    name="payment_card_add_total",
    documentation="Total number of payment card added.",
    labelnames=("channel", "provider", "route"),
    namespace=NAMESPACE
)

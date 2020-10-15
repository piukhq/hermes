from django_prometheus.middleware import PrometheusBeforeMiddleware, PrometheusAfterMiddleware
from django_prometheus.utils import TimeSince

from prometheus.labels import CustomMetrics


# the Metrics class is used as singleton so it need to be the same for both middlewares.
class CustomPrometheusBeforeMiddleware(PrometheusBeforeMiddleware):
    metrics_cls = CustomMetrics


class CustomPrometheusAfterMiddleware(PrometheusAfterMiddleware):
    metrics_cls = CustomMetrics

    def process_response(self, request, response):
        method = self._method(request)
        name = self._get_view_name(request)
        status = str(response.status_code)
        try:
            bundle_id = response.renderer_context["request"].channels_permit.bundle_id
        except (AttributeError, KeyError):
            bundle_id = "service_api_user"

        # -------------------------------- Add here custom labels metrics to collect. ------------------------------- #
        self.label_metric(
            self.metrics.requests_by_method_channel_view_and_response_status,
            request,
            method=method,
            channel=bundle_id,
            view=self._get_view_name(request),
            response_status=response.status_code,
        ).inc()

        # ----------------------------------------------------------------------------------------------------------- #
        self.label_metric(self.metrics.responses_by_status, request, response, status=status).inc()
        self.label_metric(
            self.metrics.responses_by_status_view_method,
            request,
            response,
            status=status,
            view=name,
            method=method,
        ).inc()
        if hasattr(response, "charset"):
            self.label_metric(
                self.metrics.responses_by_charset,
                request,
                response,
                charset=str(response.charset),
            ).inc()
        if hasattr(response, "streaming") and response.streaming:
            self.label_metric(self.metrics.responses_streaming, request, response).inc()
        if hasattr(response, "content"):
            self.label_metric(self.metrics.responses_body_bytes, request, response).observe(len(response.content))
        if hasattr(request, "prometheus_after_middleware_event"):
            self.label_metric(
                self.metrics.requests_latency_by_view_method,
                request,
                response,
                view=self._get_view_name(request),
                method=request.method,
            ).observe(TimeSince(request.prometheus_after_middleware_event))
        else:
            self.label_metric(self.metrics.requests_unknown_latency, request, response).inc()
        return response

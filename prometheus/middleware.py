from django.conf import settings
from django_prometheus.middleware import PrometheusAfterMiddleware, PrometheusBeforeMiddleware
from django_prometheus.utils import TimeSince

from prometheus.metrics import CustomMetrics


def _get_bundle_id(request, response=None):
    try:
        if str(request.user) == "AnonymousUser":
            # service_api_token authentication is used for internal services.
            return settings.SERVICE_API_METRICS_BUNDLE
        elif response is None:
            # handling of an exception, no channels_permit has been set, need to get the bundle from the db.
            return request.user.client.clientapplicationbundle_set.values_list("bundle_id", flat=True).first()
        else:
            # collects the bundle_id from channels_permit
            return response.renderer_context["request"].channels_permit.bundle_id or "none"
    except (AttributeError, KeyError):
        # old bink endpoint, defaults to bink bundle_id.
        return settings.BINK_BUNDLE_ID


# the Metrics class is used as singleton so it need to be the same for both middlewares.
class CustomPrometheusBeforeMiddleware(PrometheusBeforeMiddleware):
    metrics_cls = CustomMetrics


class CustomPrometheusAfterMiddleware(PrometheusAfterMiddleware):
    metrics_cls = CustomMetrics

    def process_response(self, request, response):
        method = self._method(request)
        name = self._get_view_name(request)
        status = str(response.status_code)
        bundle_id = _get_bundle_id(request, response)

        self.label_metric(self.metrics.responses_by_status, request, response, status=status).inc()
        self.label_metric(
            self.metrics.responses_by_status_view_method,
            request,
            response,
            status=status,
            view=name,
            method=method,
            channel=bundle_id,
        ).inc()
        if hasattr(response, "charset"):
            self.label_metric(self.metrics.responses_by_charset, request, response, charset=str(response.charset)).inc()
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
                channel=bundle_id,
            ).observe(TimeSince(request.prometheus_after_middleware_event))
        else:
            self.label_metric(self.metrics.requests_unknown_latency, request, response).inc()
        return response

    def process_exception(self, request, exception):
        self.label_metric(self.metrics.exceptions_by_type, request, type=type(exception).__name__).inc()
        if hasattr(request, "resolver_match"):
            name = request.resolver_match.view_name or "<unnamed view>"
            self.label_metric(self.metrics.exceptions_by_view, request, view=name).inc()
        if hasattr(request, "prometheus_after_middleware_event"):
            self.label_metric(
                self.metrics.requests_latency_by_view_method,
                request,
                view=self._get_view_name(request),
                method=request.method,
                channel=_get_bundle_id(request),
            ).observe(TimeSince(request.prometheus_after_middleware_event))
        else:
            self.label_metric(self.metrics.requests_unknown_latency, request).inc()

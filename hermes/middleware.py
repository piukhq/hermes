import logging
from time import perf_counter, process_time
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import connection
from django_prometheus.conf import NAMESPACE
from django_prometheus.middleware import PrometheusAfterMiddleware
from django_prometheus.utils import TimeSince
from prometheus_client import Counter

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.response import Response


class MiddlewareMixin(object):
    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__()

    def __call__(self, request: "Request") -> "Response":
        return self.middleware(request)

    def middleware(self, request: "Request") -> "Response":
        raise NotImplementedError("Override this method with the required logic.")


class AcceptVersion(MiddlewareMixin):
    def middleware(self, request: "Request") -> "Response":
        try:
            accept, accept_params = request.META.get("HTTP_ACCEPT").split(";", 1)
            if accept == "application/vnd.bink+json":
                request.META["HTTP_ACCEPT"] = f"application/json;{accept_params}"

        except (ValueError, AttributeError):
            pass

        response = self.get_response(request)

        try:
            response["X-API-Version"] = response.renderer_context["request"].api_version
        except AttributeError:
            pass

        return response


class TimedRequest(MiddlewareMixin):
    def middleware(self, request: "Request") -> "Response":
        start = perf_counter()
        process_start = process_time()
        response = self.get_response(request)
        process_timer = int((process_time() - process_start) * 100000)
        total_timer = int((perf_counter() - start) * 100000)
        response["X-Response-Timer"] = "".join([str(total_timer / 100), " ms"])
        response["X-Process-Timer"] = "".join([str(process_timer / 100), " ms"])
        return response


class QueryDebug(MiddlewareMixin):
    """
    This middleware will log the number of queries run
    and the total time taken for each request (with a
    status code of 200). It does not currently support
    multi-db setups.
    """

    def middleware(self, request: "Request") -> "Response":
        response = self.get_response(request)
        if settings.DEBUG and response.status_code and int(response.status_code / 100) == 2:
            total_timer = 0
            counter = 0
            for query in connection.queries:
                query_time = query.get("time")
                if query_time is None:
                    # django-debug-toolbar monkeypatches the connection
                    # cursor wrapper and adds extra information in each
                    # item in connection.queries. The query time is stored
                    # under the key "duration" rather than "time" and is
                    # in milliseconds, not seconds.
                    query_time = query.get("duration", 0)
                else:
                    query_time = float(query_time) * 1000
                total_timer += float(query_time)
                counter += 1
                sql = query.get("sql", "")
                response[f"X-SQL-{counter}"] = f"| {query_time}  | {sql} |"
            response["X-Total-Query-Timer"] = "".join([str(total_timer), " ms"])
        return response


class CustomPrometheusAfterMiddleware(PrometheusAfterMiddleware):
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.metrics = self.metrics_cls.get_instance()
        # --------------------------------------- register here custom labels --------------------------------------- #
        self.metrics.requests_by_method_channel_view_and_response_status = self.metrics.register_metric(
            Counter,
            "django_http_requests_total_by_method_channel_view_and_response_status",
            "Count of requests by method, channel, view, and response status",
            ["method", "channel", "view", "response_status"],
            namespace=NAMESPACE,
        )
        # ----------------------------------------------------------------------------------------------------------- #

    def process_response(self, request, response):
        method = self._method(request)
        name = self._get_view_name(request)
        status = str(response.status_code)
        try:
            bundle_id = response.renderer_context["request"].channels_permit.bundle_id
        except (AttributeError, KeyError):
            bundle_id = "service_api_user"

        # ---------------------------------------- Add here labels to collect --------------------------------------- #
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

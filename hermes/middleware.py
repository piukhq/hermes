import logging
from time import perf_counter, process_time
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import connection

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

import logging
from time import perf_counter, process_time

from django.conf import settings
from django.db import connection

from ubiquity.versioning import MAX_VERSION, SERIALIZERS_CLASSES

logger = logging.getLogger(__name__)


def accept_version(get_response):
    # One-time configuration and initialization.

    def middleware(request):
        # This code checks the accept header used for banking app and
        #   1)  rewrites it as application/json
        #   2)  sets request.version to parameter v= or version=  note v= is in spec but version is more standard
        #   3)  normalise version number to X.X format. ex: 1.1.4 -> 1.1

        version_number = MAX_VERSION
        try:
            accept, *accept_params = request.META.get("HTTP_ACCEPT").split(';')
            if accept and accept == "application/vnd.bink+json":
                accept_dict = {}
                for param in accept_params:
                    key, value = param.split('=', 1)
                    accept_dict.update({key: value})

                if 'v' in accept_dict:
                    version_number = accept_dict['v'][:3]

                elif 'version' in accept_dict:
                    version_number = accept_dict['version'][:3]

        except (ValueError, AttributeError):
            logger.debug(f"Unknown version format in accept header, "
                         f"defaulting the max version: {MAX_VERSION}")

        if version_number not in SERIALIZERS_CLASSES:
            logger.debug(f"Unknown version found in accept header: {version_number}, "
                         f"defaulting the max version: {MAX_VERSION}")
            version_number = MAX_VERSION

        request.META["HTTP_ACCEPT"] = "application/json;version={}".format(version_number)
        response = get_response(request)
        response['X-API-Version'] = version_number
        return response

    return middleware


def timed_request(get_response):
    # One-time configuration and initialization.

    def middleware(request):
        start = perf_counter()
        process_start = process_time()
        response = get_response(request)
        process_timer = int((process_time() - process_start) * 100000)
        total_timer = int((perf_counter() - start) * 100000)
        response["X-Response-Timer"] = "".join([str(total_timer / 100), " ms"])
        response["X-Process-Timer"] = "".join([str(process_timer / 100), " ms"])
        return response

    return middleware


def query_debug(get_response):
    """
    This middleware will log the number of queries run
    and the total time taken for each request (with a
    status code of 200). It does not currently support
    multi-db setups.
    """

    def middleware(request):
        response = get_response(request)
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

    return middleware

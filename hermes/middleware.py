from time import perf_counter, process_time


def accept_version(get_response):
    # One-time configuration and initialization.

    def middleware(request):
        # This code checks the accept header used for banking app and
        #   1)  rewites it as application/json
        #   2)  sets request.version to parameter v=,  ver= or version=  note v= is in spec but version is more standard
        #   3)  Adds /ubiquity to path so as it maps to document

        accept = request.META.get('HTTP_ACCEPT')
        version_number = '1.0'
        if accept and accept[0:25] == 'application/vnd.bink+json':
            try:
                accept, version = accept.split(";")
                if version[0:1] == 'v':                  # allow any parameter starting with v eg v= , ver=, version=
                    _, version_number = version.split('=')
            except ValueError:
                pass
            request.META['HTTP_ACCEPT'] = 'application/json;version={}'.format(version_number)
        response = get_response(request)
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
        response['X-Response-Timer'] = ''.join([str(total_timer / 100), ' ms'])
        response['X-Process-Timer'] = ''.join([str(process_timer / 100), ' ms'])
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
        if response.status_code and int(response.status_code/100) == 2:
            total_timer = 0
            counter = 0
            for query in connection.queries:
                query_time = query.get('time')
                if query_time is None:
                    # django-debug-toolbar monkeypatches the connection
                    # cursor wrapper and adds extra information in each
                    # item in connection.queries. The query time is stored
                    # under the key "duration" rather than "time" and is
                    # in milliseconds, not seconds.
                    query_time = query.get('duration', 0)
                else:
                    query_time = float(query_time) * 1000
                total_timer += float(query_time)
                counter += 1
                sql = query.get('sql', '')
                response[f'X-SQL-{counter}'] = f'| {query_time}  | {sql} |'
            response['X-Total-Query-Timer'] = ''.join([str(total_timer), ' ms'])
        return response

    return middleware

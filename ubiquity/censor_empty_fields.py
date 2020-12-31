def is_not_empty(value):
    if value or isinstance(value, (bool, int, float, list)):
        return True

    return False


def remove_empty(d):
    if not isinstance(d, (dict, list)):
        return d

    if isinstance(d, list):
        return [v for v in (remove_empty(v) for v in d) if is_not_empty(v)]

    data = {}

    # Excluding code. We still want to return the code fields and not remove it.
    # This is for cancelled, redeemed and expired vouchers.
    # Excluding cta_url as per LOY-166 spec.
    for k, v in d.items():
        if k in ("code", "cta_url"):
            data[k] = v
        else:
            if is_not_empty(v):
                data[k] = remove_empty(v)
    return data


def censor_and_decorate(func):
    def func_wrapper(*args, **kwargs):
        response = func(*args, **kwargs)

        if response.status_code in (200, 201):
            response.data = remove_empty(response.data)
            return response

        return response

    return func_wrapper


def censor_empty_values_middleware(get_response):
    def middleware(request):
        response = get_response(request)
        data_dict = remove_empty(response.data)
        response.data = data_dict
        response._is_rendered = False
        response.render()
        return response

    return middleware

def is_not_empty(value):
    if value or isinstance(value, bool) or isinstance(value, int) or isinstance(value, float):
        return True
    return False


def _remove_empty(data_dict):
    out = {}
    for k, v in data_dict.items():
        if isinstance(v, list):
            new_v = []
            for item in v:
                new_list = _remove_empty(item)
                if is_not_empty(new_list):
                    new_v.append(new_list)

            if is_not_empty(new_v):
                out.update({k: new_v})

        elif isinstance(v, dict):
            new_v = _remove_empty(v)
            if new_v:
                out.update({k: new_v})

        elif is_not_empty(v):
            out.update({k: v})

    return out


def censor_empty_values(get_response):
    def middleware(request):
        response = get_response(request)
        data_dict = _remove_empty(response.data)
        response.data = data_dict
        response._is_rendered = False
        response.render()
        return response

    return middleware

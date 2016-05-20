def validate_boolean(value):
    return value in ['0', '1']


def validate_number(value):
    try:
        float(value)
    except ValueError:
        return False
    else:
        return True

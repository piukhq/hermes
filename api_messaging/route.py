from api_messaging import api2_background


def route_message(headers: dict, message: dict):
    # Route message to core functionality. Route found in headers
    route = {
        "add_payment_card": api2_background.add_payment_card(message),
        "delete_payment_card": api2_background.delete_payment_card(message),
    }

    try:
        route[headers["X-http-path"]]
        return True
    except KeyError:
        return False

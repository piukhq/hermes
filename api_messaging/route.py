from api_messaging import api2_background
import logging
import ast

logger = logging.getLogger(__name__)


def route_message(headers: dict, message: dict):
    # Route message to core functionality. Route found in headers

    message = ast.literal_eval(message)

    route = {
        "add_payment_card": api2_background.add_payment_card,
        "delete_payment_account": api2_background.delete_payment_account,
    }

    try:
        route[headers["X-http-path"]](message)
        return True
    except KeyError:
        return False

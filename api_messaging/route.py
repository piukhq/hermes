from api_messaging import api2_background
import logging
import ast

logger = logging.getLogger(__name__)


def on_message_received(body, message):
    logger.info("API 2 message received")
    # print(f"got message: {message}  body: {body} headers: {message.headers}")
    # body is read as str from message - ast.literal eval converts back into dict
    try:
        success = route_message(message.headers, ast.literal_eval(body))
    except RuntimeError:
        if not message.acknowledged:
            message.reject()
    if not message.acknowledged:
        if success:
            message.ack()
        else:
            message.requeue()


def route_message(headers: dict, message: dict):
    # Route message to core functionality. Route found in headers

    route = {
        "add_payment_card": api2_background.add_payment_card,
        "delete_payment_account": api2_background.delete_payment_account,
    }

    try:
        route[headers["X-http-path"]](message)
        return True
    except KeyError:
        return False

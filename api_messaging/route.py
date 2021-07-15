from api_messaging import api2_background
from django.http import Http404
from django.core.exceptions import ObjectDoesNotExist
from urllib3.exceptions import RequestError
from api_messaging.exceptions import MessageReject, MessageRequeue, InvalidMessagePath

import logging
import ast

logger = logging.getLogger("Messaging")


def on_message_received(body, message):
    logger.info("API 2 message received")
    # body is read as str from message - ast.literal eval converts back into dict

    try:
        route_message(message.headers, ast.literal_eval(body))
        if not message.acknowledged:
            message.ack()

    except (KeyError, TypeError, OSError, RequestError, ObjectDoesNotExist, Http404, MessageReject):
        if not message.acknowledged:
            logger.error("Error processing message - message rejected.", exc_info=True)
            message.reject()
    except MessageRequeue:
        if not message.acknowledged:
            # Todo: Look into custom requeuing to allow for automatic retries (as requeuing adds it back to the
            #  top of the queue - we want to put it to the back, with altered headers for retry information (count,
            #  delay, time etc.) which will exponentially get longer.
            logger.error("Error processing message - message requeued.", exc_info=True)
            message.requeue()
    except Exception:
        # Catch-all for other errors
        if not message.acknowledged:
            logger.error("Error processing message - message rejected.", exc_info=True)
            message.reject()


def route_message(headers: dict, message: dict):
    # Route message to core functionality. Route found in headers

    route = {
        "add_payment_account": api2_background.add_payment_account,
        "delete_payment_account": api2_background.delete_payment_account,
    }

    try:
        route[headers["X-http-path"]](message)
    except KeyError:
        raise InvalidMessagePath

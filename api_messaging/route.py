from api_messaging import angelia_background
from django.http import Http404
from django.core.exceptions import ObjectDoesNotExist
from urllib3.exceptions import RequestError
from api_messaging.exceptions import MessageReject, MessageRequeue, InvalidMessagePath

import logging
import json

logger = logging.getLogger("Messaging")


def on_message_received(body, message):
    logger.info("Angelia message received")

    try:
        route_message(message.headers, json.loads(body))
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
        "post_payment_account": angelia_background.post_payment_account,
        "delete_payment_account": angelia_background.delete_payment_account,
        "loyalty_card_register": angelia_background.loyalty_card_register,
        "loyalty_card_add_and_auth": angelia_background.loyalty_card_add_and_auth,
    }

    try:
        route[headers["X-http-path"]](message)
    except KeyError:
        raise InvalidMessagePath

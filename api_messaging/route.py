import json
import logging
from time import sleep

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import close_old_connections
from django.http import Http404
from urllib3.exceptions import RequestError

from api_messaging import angelia_background
from api_messaging.exceptions import InvalidMessagePath, MessageReject, MessageRequeue

logger = logging.getLogger("messaging")


# Keeping it basic for now and only retry on DoesNotExist exceptions
def retry(headers: dict, message: dict, route: dict) -> None:
    for retry_count in range(settings.API_MESSAGING_RETRY_LIMIT):
        try:
            route[headers["X-http-path"]](message)
            logger.info(f"Angelia background message processed successfully: {headers['X-http-path']}")
            break
        except ObjectDoesNotExist as e:
            sleep(1)
            if retry_count + 1 == settings.API_MESSAGING_RETRY_LIMIT:
                logger.exception(f"An Angelia Background exception occurred. Traceback: {e}")
                break
            else:
                logger.info(f"Retrying function: {headers['X-http-path']}")
        except KeyError:
            raise InvalidMessagePath
        except Exception as e:
            logger.exception(f"An Angelia Background exception occurred. Traceback: {e}")
            break


def on_message_received(body, message):
    logger.info(f"Angelia message received: {message.headers.get('X-http-path')}")

    try:
        close_old_connections()
    except Exception as err:
        logger.exception("Failed to prune old connections", exc_info=err)

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
            #  Note by Martin:  I think the way to do this would be not to requeue but to write to a dead-letter queue
            #  with a ttl which when expires writes the task back on to the original queue.  Similar to what was done
            #  for celery delay feature.  This would not provide an exponential backoff since the ttl is a queue based
            #  config.  There is a RabbitMQ plug in to do delays per message but read the issues and exceptions before
            #  using in Production
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
        "loyalty_card_add_and_register": angelia_background.loyalty_card_add_and_register,
        "loyalty_card_add_auth": angelia_background.loyalty_card_add_authorise,
        "loyalty_card_add": angelia_background.loyalty_card_add,
        "loyalty_card_trusted_add": angelia_background.loyalty_card_trusted_add,
        "loyalty_card_join": angelia_background.loyalty_card_join,
        "delete_loyalty_card": angelia_background.delete_loyalty_card,
        "delete_user": angelia_background.delete_user,
        "refresh_balances": angelia_background.refresh_balances,
        "mapped_history": angelia_background.mapper_history,
        "add_auth_outcome_event": angelia_background.add_auth_outcome_event,
        "add_auth_request_event": angelia_background.add_auth_request_event,
        "sql_history": angelia_background.sql_history,
        "user_session": angelia_background.user_session,
    }

    retry(headers, message, route)

from billiard.exceptions import SoftTimeLimitExceeded
from sentry_sdk.hub import _should_send_default_pii
from sentry_sdk.integrations.django import DjangoIntegration, DjangoRequestExtractor, _set_user_info
from sentry_sdk.utils import capture_internal_exceptions

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from typing import Optional
    from typing import Callable
    from typing import Dict

    from sentry_sdk._types import EventProcessor, Event, Hint
    from django.core.handlers.wsgi import WSGIRequest


"""
These functions are to monkey patch the existing Sentry integrations for Django and Celery.
This is to allow filtering of sensitive data in performance traces, which is not easily
doable with the sentry sdk by default for some reason.
"""


def _make_celery_event_processor(task, uuid, args, kwargs, request=None):
    # type: (Any, Any, Any, Any, Optional[Any]) -> EventProcessor
    def event_processor(event, hint):
        # type: (Event, Hint) -> Optional[Event]

        with capture_internal_exceptions():
            tags = event.setdefault("tags", {})
            tags["celery_task_id"] = uuid
            extra = event.setdefault("extra", {})
            if event.get("type") == "transaction":
                extra["celery-job"] = {
                    "task_name": task.name
                }
            else:
                extra["celery-job"] = {
                    "task_name": task.name,
                    "args": args,
                    "kwargs": kwargs,
                }

        if "exc_info" in hint:
            with capture_internal_exceptions():
                if issubclass(hint["exc_info"][0], SoftTimeLimitExceeded):
                    event["fingerprint"] = [
                        "celery",
                        "SoftTimeLimitExceeded",
                        getattr(task, "name", task),
                    ]

        return event

    return event_processor


def _make_django_event_processor(weak_request, integration):
    # type: (Callable[[], WSGIRequest], DjangoIntegration) -> EventProcessor
    def event_processor(event, hint):
        # type: (Dict[str, Any], Dict[str, Any]) -> Dict[str, Any]
        # if the request is gone we are fine not logging the data from
        # it.  This might happen if the processor is pushed away to
        # another thread.
        request = weak_request()
        if request is None:
            return event

        try:
            drf_request = request._sentry_drf_request_backref()
            if drf_request is not None:
                request = drf_request
        except AttributeError:
            pass

        with capture_internal_exceptions():
            DjangoRequestExtractor(request).extract_into_event(event)

        if _should_send_default_pii():
            with capture_internal_exceptions():
                _set_user_info(request, event)

        if event.get("type") == "transaction":
            event["request"]["data"] = "[Filtered]"
            event["request"]["headers"]["Authorization"] = "[Filtered]"

        return event

    return event_processor

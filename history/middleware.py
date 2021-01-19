import logging

from django.utils.deprecation import MiddlewareMixin

from history.signals import HISTORY_CONTEXT

logger = logging.getLogger(__name__)


class HistoryRequestMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if getattr(HISTORY_CONTEXT, "channels_permit", None):
            logger.info("channels permit failed to clear from history context.")

        if getattr(HISTORY_CONTEXT, "request", None):
            logger.info("request failed to clear from history context.")

        HISTORY_CONTEXT.request = request

    def process_response(self, request, response):
        if hasattr(HISTORY_CONTEXT, "channels_permit"):
            del HISTORY_CONTEXT.channels_permit

        if hasattr(HISTORY_CONTEXT, "request"):
            del HISTORY_CONTEXT.request

        return response

    def process_exception(self, request, exception):
        if hasattr(HISTORY_CONTEXT, "channels_permit"):
            del HISTORY_CONTEXT.channels_permit

        if hasattr(HISTORY_CONTEXT, "request"):
            del HISTORY_CONTEXT.request

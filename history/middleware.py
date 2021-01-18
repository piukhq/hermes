import logging

from django.utils.deprecation import MiddlewareMixin

from history.signals import LOCAL_CONTEXT

logger = logging.getLogger(__name__)


class HistoryRequestMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if getattr(LOCAL_CONTEXT, "channels_permit", None):
            logger.info("channels permit failed to clear.")

    def process_response(self, request, response):
        if hasattr(LOCAL_CONTEXT, "channels_permit"):
            del LOCAL_CONTEXT.channels_permit

        return response

    def process_exception(self, request, exception):
        if hasattr(LOCAL_CONTEXT, "channels_permit"):
            del LOCAL_CONTEXT.channels_permit

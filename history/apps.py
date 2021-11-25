import logging

from django.apps import AppConfig
from django.conf import settings
from django.db.models import signals

logger = logging.getLogger("history")


class HistoryConfig(AppConfig):
    name = "history"

    def ready(self):
        if settings.INIT_RUNTIME_APPS or settings.TESTING:
            from history.enums import HistoryModel
            from history.serializers import load_body_serializers
            from history.signals import signal_record_history

            logger.info("Connecting History signals.")
            load_body_serializers()
            for sender in HistoryModel:
                signals.post_save.connect(signal_record_history, sender=sender.value)
                signals.pre_delete.connect(signal_record_history, sender=sender.value)
        else:
            logger.info("History signals not connected as this is either a migration or statics collection")

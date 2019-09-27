from django.apps import AppConfig
from hermes.settings import ENABLE_DAEDALUS_MESSAGING


class MessageAppConfig(AppConfig):

    name = 'daedalus_messaging'
    verbose_name = 'daedalus messaging'

    def ready(self):
        if ENABLE_DAEDALUS_MESSAGING:
            # import signal handlers - THIS IS NOT AN ERROR
            import daedalus_messaging.signals  # noqa: F401
